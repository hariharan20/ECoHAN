#! /usr/bin/env python
import rospy 
from cohan_gazebo.msg import setGoal
from geometry_msgs.msg import PoseStamped , Twist
from move_base_msgs.msg import MoveBaseGoal, MoveBaseAction
import actionlib 
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
from tf.transformations import quaternion_from_euler , euler_from_quaternion
import numpy as np
import argparse
import math
import rospkg
import time
import json
import threading
# parser = argparse.ArgumentParser()


# parser.add_argument('--scene_type' , type=str , default='open_space' , help = 'Choose one from "open_space" ,  "corridor"  , "long_bottleneck" ,  "short_bottleneck" ')

# args = parser.parse_args()
ros_pack = rospkg.RosPack()
backoff_file_path  = ros_pack.get_path('ecohan')  + '/config/backoff_locations.json'
with open(backoff_file_path, 'r') as file:
    back_off_data = json.load(file)  # Load existing data

def get_backoff_location(position):
    dists = []
    for loc in back_off_data['map']:
        center = loc['pose']['center'] 
        dist = np.linalg.norm([center[0]-position[0], center[1]-position[1]])
        dists.append(dist)
    idx = dists.index(min(dists))
    return [ back_off_data['map'][idx]['pose']['center'][0] , back_off_data['map'][idx]['pose']['center'][0]  ,  back_off_data['map'][idx]['pose']['angle']]



class scene_gen: 
    def __init__ (self):
        self.space_list = ["open_space" ,  "corridor"  , "long_bottleneck" ,  "short_bottleneck" , "corssing" , "following"]
        self.human_target_pose_msg = PoseStamped()
        self.human_target_pose_msg.header.frame_id = 'map'
        self.human_id = 1
        self.human_goal_msg = setGoal()
        self.human_goal_publisher = rospy.Publisher('/human_goals' , setGoal , queue_size= 10)
        self.pub_cmd = rospy.Publisher('/base_controller/command', Twist , queue_size=10)
        self.robot_movebase_client = actionlib.SimpleActionClient('move_base' , MoveBaseAction)
        self.robot_target_goal_msg = MoveBaseGoal()
        self.robot_target_goal_msg.target_pose.header.frame_id = 'map'
        self.robot_movebase_client.wait_for_server()
        rospy.Subscriber('base_pose_ground_truth' , Odometry , self.robot_odom_callback)
        rospy.Subscriber(f'/human{self.human_id}/odom', Odometry, self.human_odom_callback)
        # rospy.Subscriber('/clock' , Clock , self.backoff_cb)
        # rospy.Subscriber('/clock' , Clock , self.eval_scene_generator)
        rospy.Timer(rospy.Duration(0.1) , self.backoff_cb)
        rospy.Timer(rospy.Duration(0.1) , self.human_goal_setter)
        rospy.Timer(rospy.Duration(0.1) , self.robot_goal_setter)

    def robot_odom_callback(self, msg) : 
        self.last_pose = msg.pose.pose


    def human_odom_callback(self, msg):
        orien = euler_from_quaternion([msg.pose.pose.orientation.x, msg.pose.pose.orientation.y,
                                       msg.pose.pose.orientation.z, msg.pose.pose.orientation.w])
        self.human_xyt = np.array([msg.pose.pose.position.x, msg.pose.pose.position.y, orien[2]])

    def backoff_cb(self , _) :
        # rospy.loginfo('---INSIDE BACKOFF CB----')
        if rospy.get_param('back_off/robot' , False) :
            rospy.set_param('back_off/robot' , False)
            print('---inside cancel goal----')
            try : 
                self.robot_movebase_client.cancel_goal()
                print('CANCELLED GOAL')
            except :
                rospy.loginfo('UNABLE TO CANCEL GOAL')
                pass
            self.move_backward()
            self.robot_mover()
            rospy.set_param('back_off/robot' , False)
        if rospy.get_param('back_off/human' , False)  :
            print('INSIDE HUMAN BACKOFF')
            goal = get_backoff_location(self.human_xyt[:2])
            self.human_mover(goal)
            # rospy.sleep(5.0)
            time.sleep(5.0)
            print('AFTER SLEEP')
            self.human_mover()
            rospy.set_param('back_off/human' , False)
    
    def __publish_twist(self, linear: float, angular: float):
        msg = Twist()
        msg.linear.x = float(linear)
        msg.angular.z = float(angular)
        self.pub_cmd.publish(msg)

    def move_backward(self, distance=0.5, linear_vel: float = -0.5) :
    
        initial_x, initial_y = self.last_pose.position.x, self.last_pose.position.y
        rospy.loginfo('MOVING BACK')
        while True:
            if self.last_pose is None:
                self.__publish_twist(0.0, 0.0)
                raise RuntimeError("Failed to get current odometry data.")

            current_x, current_y = self.last_pose.position.x, self.last_pose.position.y
            traveled_distance = math.sqrt((current_x - initial_x) ** 2 + (current_y - initial_y) ** 2)
            if traveled_distance >= distance:
                rospy.loginfo('MOVED BACK')
                self.__publish_twist(0.0, 0.0)
                break

            self.__publish_twist(linear_vel, 0)
            time.sleep(0.1) 

    def robot_mover(self , pose=None) : 
        if pose is None : 
            pose = self.robot_last_pose
        self.robot_target_goal_msg.target_pose.header.stamp = rospy.Time.now()
        self.robot_target_goal_msg.target_pose.pose.position.x = pose[0]
        self.robot_target_goal_msg.target_pose.pose.position.y = pose[1]
        quat = quaternion_from_euler(0 , 0 , pose[2])
        self.robot_target_goal_msg.target_pose.pose.orientation.x  = quat[0]
        self.robot_target_goal_msg.target_pose.pose.orientation.y  = quat[1]
        self.robot_target_goal_msg.target_pose.pose.orientation.z  = quat[2]
        self.robot_target_goal_msg.target_pose.pose.orientation.w  = quat[3]
        self.robot_movebase_client.send_goal(self.robot_target_goal_msg)
        while not self.is_close_to_goal(pose , [self.last_pose.position.x, self.last_pose.position.y]) :
            if rospy.get_param('back_off/robot' , False) :
                break
            time.sleep(0.1)
        rospy.loginfo('ROBOT REACHED GOAL')
        
    def human_mover(self, pose=None) :
        if pose is None : 
            pose = self.human_last_pose 
        self.human_goal_msg.id = self.human_id
        self.human_target_pose_msg.header.stamp = rospy.Time.now()
        self.human_target_pose_msg.pose.position.x = pose[0]
        self.human_target_pose_msg.pose.position.y = pose[1]
        quat = quaternion_from_euler(0 , 0  , pose[2])
        self.human_target_pose_msg.pose.orientation.x  = quat[0] 
        self.human_target_pose_msg.pose.orientation.y  = quat[1] 
        self.human_target_pose_msg.pose.orientation.z  = quat[2] 
        self.human_target_pose_msg.pose.orientation.w  = quat[3] 
        self.human_goal_msg.goal = self.human_target_pose_msg
        self.human_goal_publisher.publish(self.human_goal_msg)
        while not self.is_close_to_goal(pose , self.human_xyt) :
            rospy.loginfo(self.is_close_to_goal(pose , self.human_xyt))
            if rospy.get_param('back_off/human' , False) :
                break
            time.sleep(0.1)
        rospy.loginfo('HUMAN REACHED GOAL')
    
    def is_close_to_goal(self , pose_1 , pose_2) :
        # print(pose_1 , pose_2)
        diff = math.sqrt((pose_1[0] - pose_2[0])**2 + (pose_1[1] - pose_2[1])**2)
        # rospy.loginfo(diff)
        if diff < 0.2: 
            return True
        else : 
            return False

    def human_goal_setter(self , _ ): 
        print('INSIDE HUMAN GOAL SETTER')

        setting = rospy.get_param('scene_type' , 'open_space')
        if setting == self.space_list[0] :  
            human_start_pose = [ 10 , 16, -1.57]
            human_goal_pose = [1.5 , 16.0 ,-1.57]
        elif setting == self.space_list[1] : 
            human_start_pose = [1.5 , 14 , 0]
            human_goal_pose =   [2 , 2 , 0]
        elif setting == self.space_list[2] : 
            human_start_pose =[ 1, 4.5 , 1.57]
            human_goal_pose =[ 1 , -4, 1.57]
        elif setting == self.space_list[3]  :
            human_start_pose = [ 1 , 9 ,  0.0 ] 
            human_goal_pose  = [ 5 , 2.5 , 1.57]
        else :
            print('Provide a valid scene name , REFER to list of scenes') 
            pass
        # print('SCENE SELECTED')
        self.human_last_pose = human_start_pose
        self.human_mover()
        self.human_last_pose = human_goal_pose
        self.human_mover()


    def robot_goal_setter(self , _): 
        setting = rospy.get_param('scene_type' , 'open_space')
        if setting == self.space_list[0] :  
            robot_start_pose = [1.5 , 16.0 , 0.0]
            robot_goal_pose = [10 , 16, 0.0 ]
        elif setting == self.space_list[1] : 
            robot_start_pose = [2 , 2 , 1.57]
            robot_goal_pose = [1.5 , 14 , 1.57]
        elif setting == self.space_list[2] : 
            robot_start_pose =[ 1 , -4,  0]
            robot_goal_pose =[ 1, 4.5  ,  0]
        elif setting == self.space_list[3]  :
            robot_start_pose = [ 5 , 2.5 , 3.14] 
            robot_goal_pose  = [1 , 9 , 1.57]
        else :
            print('Provide a valid scene name , REFER to list of scenes') 
            pass
        self.robot_last_pose = robot_start_pose
        self.robot_mover()
        self.robot_last_pose = robot_goal_pose
        self.robot_mover()



if __name__ == "__main__" :
    rospy.init_node('scene_gen')
    obj = scene_gen()
    # obj.eval_scene_generator()
    rospy.loginfo('I AM HERE')
    rospy.spin()
    # while not rospy.is_shutdown():
    #     obj.eval_scene_generator()