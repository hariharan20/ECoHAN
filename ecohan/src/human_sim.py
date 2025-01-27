#! /usr/bin/env python
import rospy 
from std_msgs.msg import String
import yaml
import random
import rospkg
ros_pack = rospkg.RosPack()

class human_sim:
    def __init__(self) : 
        self.dialogue_publisher = rospy.Publisher('/to_robot' , String , queue_size= 10)
        dialogue_location  = ros_pack.get_path('ecohan')  + '/config/human_dialogues.yaml'
        with open(dialogue_location , 'r') as f :
            yaml_data = yaml.safe_load(f)
        self.all_data = []
        self.all_data.append(yaml_data['relaxed'])
        self.all_data.append(yaml_data['hurry'])
        
    def publisher(self) :
        rospy.set_param('robot_spoken' , False)
        rospy.sleep(1)
        urgence_type = random.choice([0 , 1])
        if urgence_type == 0  :
            rospy.set_param('back_off/human' , True)
        elif urgence_type == 1 : 
            pass
        dialogue = random.choice(self.all_data[urgence_type])
        print(dialogue)
        self.dialogue_publisher.publish(String(dialogue))
        print('published')
        while not rospy.get_param('robot_spoken' , False ) :
            rospy.sleep(0.1)


if __name__ == "__main__" : 
    rospy.init_node('human_simulator_node')
    obj = human_sim()
    for i in range(20) :
        obj.publisher()
