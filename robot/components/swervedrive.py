import math
from networktables import NetworkTable


from robotpy_ext.common_drivers import navx

class SwerveDrive:
    def __init__(self, *args, **kwargs):
        """Constructor for SwerveDrive.

        4 SwerveModules should be passed in order to dirve

        When positional arguments are used, these are the two accepted:
        
        - rearRightModule, rearLeftModule, frontRightModule, frontLeftModule
        - rearRightModule, rearLeftModule, frontRightModule, frontLeftModule, navx (if field centric)

        Possible keyword arguments are:
        
        - field_centic (sets field_centric on)
        - allow_reverse (sets each module to allow reverse direction)
        - debugging (pushes more NetworkTables variables)
        """
                
        self.sd = NetworkTable.getTable('SmartDashboard')

        self.modules = [args[0],args[1],args[2],args[3]]
        self.module_speeds = [0,0,0,0]
        self.module_angles = [0,0,0,0]
        
        self.navx = None
        
        if(len(args) == 5):
            self.navx = navx
        
        self.field_centric = kwargs.pop("field_centric", False)
        self.allow_reverse = kwargs.pop("allow_reverse", False)
        self.debugging = kwargs.pop("debugging", False)
        self.squared_inputs = kwargs.pop("squared_inputs", False)
        
        self.lock_rotation = False
        self.lock_rotation_axies = self.sd.getAutoUpdateValue("drive/drive/LockRotationAxies", 8);

        self.set_chasis_deminsions(22.5, 18)
        
        self.max_drive_speed = self.sd.getAutoUpdateValue("drive/drive/MaxDriveSpeed", 1)
        self.lower_input_thresh = self.sd.getAutoUpdateValue("drive/drive/LowDriveThresh", 0.1)
        
        self.rotation_multiplyer = self.sd.getAutoUpdateValue("drive/drive/RotationMultiplyer", 0.75)
        self.xy_multiplyer = self.sd.getAutoUpdateValue("drive/drive/XYMultiplyer", 1)


    def set_chasis_deminsions(self, length, width):
        '''
        Sets the ratio to be used in movement calculations
        '''

        self.length = length
        self.width = width

        self.r = math.sqrt((self.length * self.length)+(self.width + self.width))

    def set_allow_reverse(self, value):
        self.allow_reverse = value
        
        for module in self.modules:
            module.set_allow_reverse(self.allow_reverse)
        
    def is_allow_reverse(self):
        return self.allow_reverse
    
    def set_field_centric(self, value):
        if value:
            self.navx.reset()
        self.field_centric = value
        
    def is_field_centric(self):
        return self.field_centric
    
    def set_debugging(self, value):
        self.debugging = value
        
        for module in self.modules:
            module.set_debugging(self.debugging)
            
    def is_debugging(self):
        return self.debugging
    
    def set_locking_rotation(self, boolean):
        self.lock_rotation = boolean
        
    def is_locking_rotation(self):
        return self.lock_rotation
        
    @staticmethod
    def square_input(input):
        if input >= 0.0:
            input = (input * input)
        else:
            input = -(input * input)
            
        return input
    
    def move(self, fwd, strafe, rcw):
        '''
        Calulates the speed and angle for each wheel given the requested movement
        :param fwd: the requested movement in the Y direction 2D plan
        :param strafe: the requested movement in the X direction of the 2D plan
        :param rcw: the requestest magnatude of the rotational vector of a 2D plan
        '''
        
        if self.squared_inputs:
            fwd = self.square_input(fwd)
            strafe = self.square_input(strafe)
            rcw = self.square_input(rcw)
        
        fwd *= self.xy_multiplyer.value
        rcw *= self.rotation_multiplyer.value
        
        #Does nothing if the values are lower than the input thresh
        if (abs(fwd) < self.lower_input_thresh.value) and (abs(strafe) < self.lower_input_thresh.value) and (abs(rcw) < self.lower_input_thresh.value):
            self.module_speeds = [0,0,0,0]
            
            return
        
        
        #Locks the wheels to certain intervals if locking is true
        if self.lock_rotation:
            interval = 360/self.lock_rotation_axies.value
            half_interval = interval/2
            
            #Caclulates the radius (speed) from the give x and y
            r = math.sqrt((fwd ** 2) + (strafe ** 2))
            
            #Gets the degree from the given x and y
            deg = math.degrees(math.atan2(fwd, strafe)) 
            
            #Corrects the degreee to one of 8 axies
            remainder = deg % interval            
            if remainder >= half_interval:
                deg += interval - remainder
            else:
                deg -= remainder
                
            #Gets the fwd/strafe values out of the new deg
            theta = math.radians(deg)
            fwd = math.sin(theta)*r
            strafe = math.cos(theta)*r
            
        
        if(self.field_centric):
            theta = math.radians(360-self.navx.yaw)
            
            fwdX = fwd * math.cos(theta)
            fwdY = (-fwd) * math.sin(theta) #TODO: verify and understand why fwd is neg
            strafeX = strafe * math.cos(theta)
            strafeY = strafe * math.sin(theta)
            
            fwd = fwdX + strafeY
            strafe = fwdY + strafeX

        #Velocities per quadrant
        leftY = fwd - (rcw * (self.width / self.r))
        rightY = fwd + (rcw * (self.width / self.r))
        frontX = strafe + (rcw * (self.length / self.r))
        rearX = strafe - (rcw * (self.length / self.r))

        #Calculate the speed and angle for each wheel given the combination of the corrisponding quadrant vectors
        fr_speed = math.sqrt((rightY ** 2) + (frontX ** 2))
        fr_angle = math.degrees(math.atan2(frontX, rightY))

        fl_speed = math.sqrt((leftY ** 2) + (frontX ** 2))
        fl_angle = math.degrees(math.atan2(frontX, leftY))

        rl_speed = math.sqrt((leftY ** 2) + (rearX ** 2))
        rl_angle = math.degrees(math.atan2(rearX, leftY))

        rr_speed = math.sqrt((rightY ** 2) + (rearX ** 2))
        rr_angle = math.degrees(math.atan2(rearX, rightY))

        #Assigns the speeds and angles in lists. MUST BE IN THIS ORDER
        requested_module_speeds = [fr_speed, fl_speed, rl_speed, rr_speed]
        requested_module_angles = [fr_angle, fl_angle, rl_angle, rr_angle]

        #Finds the current max speed
        max_speed = 0
        for speed in requested_module_speeds:
            if speed > max_speed:
                max_speed = speed
        
        #Normalises values if any speed is greater then the max   
        if max_speed > self.max_drive_speed.value:
            precent_over = (max_speed-self.max_drive_speed.value)/max_speed
            precent_held = 1-precent_over
            
            max_speed *= precent_held
            
            for i, speed in enumerate(requested_module_speeds):
                requested_module_speeds[i] = speed * precent_held
        
        self.module_speeds = requested_module_speeds
        self.module_angles = requested_module_angles

    def doit(self):
        '''
        Sends the speeds and angles to each corrisponding wheel module.
        Excutes the doit in each wheel module.
        '''
        self.update_smartdash()

        for i, module in enumerate(self.modules):
            module.move(self.module_speeds[i], self.module_angles[i])
        self.module_speeds = [0,0,0,0]
        #self.module_angles = [0,0,0,0]

        for module in self.modules:
            module.doit()

    def update_smartdash(self):
        '''
        Pushes some interal variables for debugging.
        '''
        self.sd.putNumber("drive/drive/GyroAngle", self.navx.yaw)
        self.sd.putBoolean("drive/drive/FieldCentric", self.field_centric)
        self.sd.putBoolean("drive/drive/AllowReverse", self.allow_reverse)
        self.sd.putBoolean("drive/drive/LockRotation", self.lock_rotation)
        
        for module in self.modules:
            module.update_smartdash()
            
        
        
        if self.debugging:
            for i, angle in enumerate(self.module_angles):
                self.sd.putNumber("drive/drive/ Angle %s" % i, angle)
                
            #self.sd.putNumber("drive/drive/MaxDriveSpeed", self.max_drive_speed)

        


