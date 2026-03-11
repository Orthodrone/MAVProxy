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

import random

import threading

from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_util
from MAVProxy.modules.lib import mp_settings
from MAVProxy.modules.lib import live_graph
from MAVProxy.modules.lib import multiproc

from dash import Dash, html, dcc, MATCH, State, ALL
import dash_daq as daq
from dash.dependencies import Input, Output

import math
from datetime import datetime

#pdb.set_trace()

GUARD_MAX_PAST_VALUES = 10
DEBUG_PLOT = True
DEBUG_MODE = True
WARNING_LEVELS = ["INFORMATION","WARNING","CRITICAL"]

vehicle_config = None
valuestate = {}

def debug_print(str):
    if(DEBUG_MODE):
        print(str)

def get_compound_index(message_type,fieldname):
    return ".".join([message_type,fieldname])

def split_compound_index(index):
    return index.split(".")

def get_Gauge_from_fieldobject(message_type,field_object):
    if(field_object["lower_limit"]) == None:
        lower_limit = field_object["field_gauge_min"]
    else:
        lower_limit = field_object["lower_limit"]
        
    if(field_object["upper_limit"]) == None:
        upper_limit = field_object["field_gauge_max"]
    else:
        upper_limit = field_object["upper_limit"]
    
    try:
        label = field_object["field_label"]
    except KeyError:
        label = field_object["field_name"]
        
    field_id = get_compound_index(message_type=message_type,fieldname=field_object["field_name"])
    gauge_object = daq.Gauge(
    id={'type': 'gauge',
        'field_id':field_id},
    label=label,
    min=field_object["field_gauge_min"], max=field_object["field_gauge_max"],
    value=0,
    units=field_object["field_gauge_unit"],
    showCurrentValue=True,
    color={
        "gradient": False,
        "ranges": {
            "#F20000":[field_object["field_gauge_min"],lower_limit],
            "green": [lower_limit, upper_limit],
            "#FF0000":[upper_limit,field_object["field_gauge_max"]]
        },
    })
    return gauge_object


def _start_dash_app():
    """Separater Thread für den Dash Webserver."""
    app = Dash(__name__)
    group_divs = []
    global vehicle_config
    for message_object in vehicle_config["guarded_messages"]:
        field_divs = []
        group_divs.append(
            html.Div(children=[
                html.H2(message_object["message_type"]),
                html.Div(children=field_divs,style={"display":"flex","flex-direction":"row","align-items":"center"}),
            ],style={"align-items":"center"})
        )
        
        for field_object in message_object["fields"]:
            field_divs.append(get_Gauge_from_fieldobject(message_object["message_type"],field_object))
            
    group_divs.append(dcc.Interval(id=("tick"), interval=500, n_intervals=0))
    #group_divs.append(html.Button('UPDATE', id='tick'))
    app.layout = html.Div(children=group_divs)
    
    @app.callback(
        Output({'type': 'gauge', 'field_id': ALL}, 'value'),
        State({'type': 'gauge', 'field_id': ALL}, 'id'),
        Input('tick', 'n_intervals')        
    )
    def updateGauge(values,ids):
        #print("Updated Gauge Fieldname " + str(id["field_name"]))
        debug_print(values)
        global valuestate
        out = []
        for n,value in enumerate(values):
            debug_print(value["field_id"])
            try:
                out.append(valuestate[value["field_id"]])
            except KeyError:
                out.append(0)
                print("KEY Error: " +  value["field_id"])
        return out
    
    # WICHTIG: neue Dash Version → app.run()
    app.run(debug=False, port=8050, host="0.0.0.0")
    
class Guard(mp_module.MPModule):
    """Guard Main Module
    Args:v
        mp_module (_type_): _description_v
    """
    def __init__(self, mpstate):
        """Initialise module"""
        super(Guard, self).__init__(mpstate, "Guard", "")
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
        
    def create_WatchDogObject(self,message_object,object_type,field_object=None):
        debug_print(field_object)
        
        if(object_type == "value"):
            self.watchdog_holder.append(
                Value_WatchDog(
                    message_type=message_object["message_type"],
                    holderobject=self,
                    field_name=field_object["field_name"],
                    lower_limit=field_object["lower_limit"],
                    upper_limit=field_object["upper_limit"],
                    mov_average_percent=field_object["mov_average_percent"],
                    warning_level=field_object["warning_level"]
                )
            )
            
        if(object_type == "status"):
            self.watchdog_holder.append(
                Status_WatchDog(
                    holderobject=self,
                    message_type=message_object["message_type"],
                    field_name=message_object["status_field_name"],
                    status_table = message_object["status_field_values"]
                    )
            )

    def handle_cmd(self, args):
        '''handle general commands and call command functions'''
        debug_print(args)
        if len(args) == 0:
            print(self.cmd_help())
        elif args[0] == "status":
            self.cmd_status()
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
        
    #def cmd_add_guard(self,args):
    #    ''' Add Limits to Function'''
    #    limits = [float(args[3]),float(args[4])]
    #    self.watchdog_holder.append(
    #        Value_WatchDog(
    #            message_type=args[1],
    #            field_name=args[2],
    #            lower_limit=min(limits),
    #            upper_limit=max(limits),
    #            mov_average_percent=args[5]
    #        )
    #    )     
           
    def cmd_load_config(self,args):
        ''' load limit function from config file'''
        group_divs = []
        
        with open(args[1]) as f:
            field_divs = []
            global vehicle_config
            vehicle_config = json.load(f)
            i = 0

            for message_object in vehicle_config["guarded_messages"]:
                # Try Creation of Status Object  if defined
                try:
                    self.create_WatchDogObject(message_object=message_object,object_type="status")
                    print("Added Status Watchdog")
                except KeyError:
                    pass                    
                
                # Create Value Watchdogs
                for field_object in message_object["fields"]:
                    self.create_WatchDogObject(message_object=message_object,field_object=field_object,object_type="value")
                    i = i + 1
        debug_print("Loaded " + str(i) + " Guard Limits for System " + vehicle_config["System Name"])      
    
    def cmd_show(self,args):
        '''Starts the Visualisation'''
        if (vehicle_config != None):
            self.console.writeln("Gauge: Starte Dash Webserver auf http://localhost:8050 ...")
            self._dash_thread = threading.Thread(target=_start_dash_app, daemon=True)
            self._dash_thread.start()
        else:
            self.say("ERROR: Load a Vehicle Config before starting the Visualisation")
            print("ERROR: Load a Vehicle Config before starting the Visualisation")
        return
 
        
    def mavlink_packet(self, msg):
        '''handle mavlink packets'''
        if(msg.get_type() == "HEARTBEAT"):
            self.armed_state = bool(msg.to_dict()["base_mode"] >> 7)
            
        for dog in self.watchdog_holder:
            if(dog.message_type == msg.get_type()):
                dog.update(msg)
                    
                    
                    
class Status_WatchDog():
    def __init__(self,holderobject,message_type,field_name,status_table):
        self.holderobject = holderobject
        self.message_type = message_type
        self.fieldname = field_name
        self.status_table = status_table
        self.compound_index = get_compound_index(self.message_type,self.fieldname)
        
    def update(self,msg):
        msg_dict = msg.to_dict()
        global valuestate
        valuestate[self.compound_index] = [] # clear the current status
        #pdb.set_trace()
        print("Status Update Called")

        statuscode = msg_dict[self.fieldname]
        for i,bit in enumerate(reversed(bin(statuscode)[2:])):
            if(int(bit) == 1):
                status_config = self.status_table[i]
                print(status_config)
                #breakpoint()
                self.notify(status_config=status_config)
                valuestate[self.compound_index].append(status_config)
                
    def notify(self,status_config):
        #if(status_config[3] >= 1):
        self.holderobject.say(str(WARNING_LEVELS[status_config[3]] + ": " + str(status_config[1])))
        print(str(WARNING_LEVELS[status_config[3]] + ": " + str(status_config[1])))
            
class Value_WatchDog():
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

    def update(self,msg):
        """Updates the Watchdog with mavlink Packet"""
        #debug_print("Updated Dog with Message Type: %s " % msg.get_type() )

        msg_dict = msg.to_dict()
        current_value = msg_dict[self.field_name]
        
        
        global valuestate
        valuestate[get_compound_index(self.message_type,self.field_name)]  = current_value
        #debug_print(valuestate)
        
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
            self.update_average(value)
            if( value > self.upper_limit_avg or value < self.lower_limit_avg):
                return True
            
        return False

    def raisealarm(self):
        self.holderobject.say(str(WARNING_LEVELS[self.warning_level] + ": " + str(self.field_name) + " out of set Boundary"))

    def update_average(self,value):
        if (value == None):
            self.holderobject.say(("Value of field " + str(self.field_name) + " is None"))
            return False
        
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
