#!/usr/bin/env python
'''
module Guardian

Guards from Parameters running out of Defined Ranges, alerts the user if a range is exceeded

Commands:
guard add Range [ParameterName] [limit1] [limit2]
TODO:
Implement Generator Status Check 

'''
import os
import os.path
import sys
from pymavlink import mavutil
import errno
import time
import json
import pdb

from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_util
from MAVProxy.modules.lib import mp_settings
from MAVProxy.modules.lib import live_graph
from MAVProxy.modules.lib import multiproc

import math
from datetime import datetime

#pdb.set_trace()

GUARD_MAX_PAST_VALUES = 10
DEBUG_PLOT = True
WARNING_LEVELS = ["INFORMATION","WARNING","CRITICAL"]



class Guard(mp_module.MPModule):
    """Guard Main Module
    Args:
        mp_module (_type_): _description_
    """
    def __init__(self, mpstate):
        """Initialise module"""
        super(Guard, self).__init__(mpstate, "Guard", "")
        #print("Guard loaded <3")
        self.say("Guard loaded <3")
        self.mpstate=mpstate

        self.watched_mtypes = []
        self.watchdog_holder = []
        self.armed_state = False


        self.Guard_settings = mp_settings.MPSettings(
            [ ('verbose', bool, False),
          ])
        self.add_command('guard', self.handle_cmd, "Guard module", [
            'status',
            'add (VALUE) (Limit1) (Limit2)'
            ])
        
        
       
    def handle_cmd(self, args):
        '''handle general commands and call command functions'''
        print(args)
        if len(args) == 0:
            print(self.cmd_help())
        elif args[0] == "status":
            self.cmd_status()
        #elif args[0] == "add":         #deactivated
        #    self.cmd_add_guard(args)
        elif args[0] == "show":
            self.cmd_show(args)
        elif args[0] == "load":
            self.cmd_load_config(args)  
        else:
            print(self.cmd_help())
            
    def cmd_help(self):
        '''show help on command line options'''
        return "Usage: guard add <messagetype> <value> <lower limit> <upper limit> <moving average percentage>"
    
    def cmd_status(self):
        '''returns information about module'''
        print("WatchDogs:")
        for dog in self.watchdog_holder:
            print("MType: ",str(dog.message_type) + " Parameter: " + str(dog.field_name))
        
            
    def cmd_add_guard(self,args):
        ''' Add Limits to Function'''
        limits = [float(args[3]),float(args[4])]      
        dog = WatchDog(message_type=args[1],
                       field_name=args[2],
                       lower_limit=min(limits),
                       upper_limit=max(limits),
                       mov_average_percent=args[5])
        self.watchdog_holder.append(dog)     
           
    def cmd_load_config(self,args):
        ''' load limit function from config file'''
        with open(r"C:\Users\Orthodrone\AppData\Local\.mavproxy\guard_limits.json") as f:
            json_config = json.load(f)
            i = 0
            for message_object in json_config["guarded_messages"]:
                for field_object in message_object["fields"]:
                    print(field_object)
                    dog = WatchDog(message_type=message_object["message_type"],
                                   holderobject=self,
                                field_name=field_object["field_name"],
                                lower_limit=field_object["lower_limit"],
                                upper_limit=field_object["upper_limit"],
                                mov_average_percent=field_object["mov_average_percent"],
                                warning_level=field_object["warning_level"])
                    self.watchdog_holder.append(dog)
                    i = i + 1
        print("Loaded " + str(i) + " Guard Limits for System " + json_config["System Name"])      
    
    def cmd_show(self,args):
        '''Placeholder'''
        return
 
        
    def mavlink_packet(self, msg):
        '''handle mavlink packets'''
        if(msg.get_type() == "HEARTBEAT"):
            self.armed_state = bool(msg.to_dict()["base_mode"] >> 7)
            #breakpoint()
            
            
        for dog in self.watchdog_holder:
            if(dog.message_type == msg.get_type()):
                dog.update(msg)
                    
                    
class WatchDog():
    def __init__(self,holderobject,message_type,field_name,lower_limit=None,upper_limit=None,mov_average_percent=None,warning_level="INFORMATION"):
        """Initialises the Watchdog Object

        Args:
            message_type (String): Message Type
            field_name (String): Field Name
        """
        self.message_type = message_type
        self.field_name = field_name
        self.lower_limit = lower_limit
        self.upper_limit = upper_limit
        self.mov_average_percent = mov_average_percent
        self.warning_level = warning_level
        self.holderobject = holderobject
        
        self.past_values = []
        self.average = None
        

        graphfields = [self.field_name]
        if(self.mov_average_percent != None):
            graphfields.append("Average")
            graphfields.append("Lower Boundry")
            graphfields.append("Upper Boundry")

        if(self.lower_limit != None):
            graphfields.append("lower Limit")
        if(self.upper_limit != None):
            graphfields.append("upper Limit")
            
            
        self.livegraph = live_graph.LiveGraph(graphfields,title=self.field_name)

    def update(self,msg):
        """Updates the Watchdog with mavlink Packet"""
        #print("Updated Dog with Message Type: %s " % msg.get_type() )
        msg_dict = msg.to_dict()
        current_value = msg_dict[self.field_name]
        
        
        graph_values = [current_value]
        if (self.mov_average_percent != None):
            self.update_average(current_value)
            
            graph_values.append(self.average)
            graph_values.append(self.lower_limit_avg)
            graph_values.append(self.upper_limit_avg)

        
        if(self.lower_limit != None):
            graph_values.append(self.lower_limit)
        if(self.upper_limit != None):
            graph_values.append(self.upper_limit)
            
        self.livegraph.add_values(graph_values)
        
        if(self.is_outof_limits(current_value)):
            self.raisealarm()
        
    def is_outof_limits(self,value):
        """Checks for Breach of Limits"""
        ## Check for Arm Condition
        
        if (not self.holderobject.armed_state):
            return False
            
        ## Check for actual flight conditions
        if(self.lower_limit != None):
            if(value < self.lower_limit):
                return True 
            
        if(self.upper_limit != None):
            if(value > self.upper_limit):
                return True
            
        if (self.mov_average_percent != None):
            if( value > self.upper_limit_avg or value < self.lower_limit_avg):
                return True
            
        return False

    def raisealarm(self):
        self.holderobject.say(str(WARNING_LEVELS[self.warning_level] + ": " + str(self.field_name) + " out of set Boundary"))

    def update_average(self,value):
        self.past_values.append(value)
        if(len(self.past_values) > GUARD_MAX_PAST_VALUES):
            self.past_values.pop(0)
            
        sum = 0
        for value in self.past_values:
            sum = sum + value
        self.average = (sum / len(self.past_values))
        self.upper_limit_avg = self.average * ( 1 + (self.mov_average_percent/100))
        self.lower_limit_avg = self.average * ( 1 - (self.mov_average_percent/100))

def init(mpstate):
    '''initialise module''' 
    return Guard(mpstate)
