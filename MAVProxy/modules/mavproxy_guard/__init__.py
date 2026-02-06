#!/usr/bin/env python
'''
module Guard

Guards from Parameters running out of Defined Ranges, alerts the user if a range is exceeded

Commands:
guard add Range [ParameterName] [limit1] [limit2]
TODO:
Implement Generator Status Check 

'''

#from pymavlink import mavutil
#import errno
#import time
import json
#import pdb

import threading

from MAVProxy.modules.lib import mp_module
#from MAVProxy.modules.lib import mp_util
from MAVProxy.modules.lib import mp_settings

from MAVProxy.modules.mavproxy_guard import Value_Watchdog, _start_dash_app, get_Gauge_from_fieldobject

GUARD_MAX_PAST_VALUES = 10
DEBUG_PLOT = True
DEBUG_MODE = False
WARNING_LEVELS = ["INFORMATION","WARNING","CRITICAL"]

valuestate = {}

def debug_print(str):
    if(DEBUG_MODE):
        print(str)

    
class Guard(mp_module.MPModule):
    """Guard Main Module
    Args:
        mp_module (_type_): _description_
    """
    def __init__(self, mpstate):
        """Initialise module"""
        super(Guard, self).__init__(mpstate, "Guard", "")
        self.say("Guard loaded <3")

        self.watchdog_holder = []
        self.armed_state = False
        
        self.console.writeln("Gauge: Starte Dash Webserver auf http://localhost:8050 ...")
        self._dash_thread = threading.Thread(target=_start_dash_app, daemon=True)
        self._dash_thread.start()

        self.Guard_settings = mp_settings.MPSettings(
            [ ('verbose', bool, False),
          ])
        self.add_command('guard', self.handle_cmd, "Guard module", [
            'status',
            'add (VALUE) (Limit1) (Limit2)'
            ])
        
        
       
    def handle_cmd(self, args):
        '''handle general commands and call command functions'''
        debug_print(args)
        if len(args) == 0:
            print(self.cmd_help())
        elif args[0] == "status":
            self.cmd_status()
        #elif args[0] == "add":         #deactivated
        #    self.cmd_add_guard(args)
        elif args[0] == "show":
            self.cmd_show(args)
        elif args[0] == "ToggleDebug":
            global DEBUG_MODE
            DEBUG_MODE = not DEBUG_MODE
            print("Debug Mode:" + str(DEBUG_MODE))
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
        dog = Value_Watchdog(message_type=args[1],
                       field_name=args[2],
                       lower_limit=min(limits),
                       upper_limit=max(limits),
                       mov_average_percent=args[5])
        self.watchdog_holder.append(dog)     
           
    def cmd_load_config(self,args):
        ''' load limit function from config file'''
        group_divs = []
        with open(r"C:\Users\Orthodrone\AppData\Local\.mavproxy\guard_config.json") as f:
            field_divs = []
            json_config = json.load(f)
            i = 0
            for message_object in json_config["guarded_messages"]:
                for field_object in message_object["fields"]:
                    debug_print(field_object)
                    dog = Value_Watchdog(message_type=message_object["message_type"],
                                   holderobject=self,
                                field_name=field_object["field_name"],
                                lower_limit=field_object["lower_limit"],
                                upper_limit=field_object["upper_limit"],
                                mov_average_percent=field_object["mov_average_percent"],
                                warning_level=field_object["warning_level"])
                    self.watchdog_holder.append(dog)
                    i = i + 1
        debug_print("Loaded " + str(i) + " Guard Limits for System " + json_config["System Name"])      
    
    def cmd_show(self,args):
        '''Placeholder'''
        return
 
        
    def mavlink_packet(self, msg):
        '''handle mavlink packets'''
        if(msg.get_type() == "HEARTBEAT"):
            self.armed_state = bool(msg.to_dict()["base_mode"] >> 7)
            
        for dog in self.watchdog_holder:
            if(dog.message_type == msg.get_type()):
                dog.update(msg)


def init(mpstate):
    '''initialise module''' 
    return Guard(mpstate)
