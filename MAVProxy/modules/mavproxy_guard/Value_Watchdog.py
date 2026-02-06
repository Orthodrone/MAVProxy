                 
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
        valuestate[self.field_name]  = current_value
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