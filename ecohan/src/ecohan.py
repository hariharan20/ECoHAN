#! /usr/bin/env python
import rospy
from std_msgs.msg import String
import yaml
import rospkg
import time
from rosgraph_msgs.msg import Clock
from llm_chains import  *
ros_pack = rospkg.RosPack()
from cohan_attr.msg import attr

class robot_node:
    def __init__(self)  :
        self.dialogue_history = []
        rospy.set_param('robot_is_listening' , True)
        self.convo_started_by_human = False
        rospy.Subscriber('/to_robot' , String  , self.human_speech_cb)
        rospy.Subscriber('/clock' , Clock ,  self.proactive_cb )
    
    def robot_speech(self , statement):
        print(statement)
        self.dialogue_history.append('robot said  : ' + str(statement))
        #TODO: Put up some TTS calls here

    def human_speech(self , statement) :
        self.dialogue_history.append('human said  : ' + str(statement))


    def proactive_cb(self , _ ):
        if rospy.get_param('start_convo' , False) and  (not self.convo_started_by_human) :
            rospy.set_param('robot_is_listening' , False)
            number_of_tries = 0
            self.dialogue_history = []
            convo_over = False
            # robot_speech = rospy.wait_for_message('/cohan_attr/full_text' , String  , timeout= 1.0) # TODO: Remove the full_text and get attributes from attr.py
            try :
                attr_msg = rospy.wait_for_message('/cohan_attr/attr'  , attr , 2.0)
                rospy.loginfo('GOT ATTR')
                # rospy.logerr([attr_msg.time_to_cross , attr_msg.distance_while_crossing , attr_msg.direction_of_crossing])
                robot_speech = attr_convo([attr_msg.time_to_cross , attr_msg.distance_while_crossing , attr_msg.direction_of_crossing])
                rospy.loginfo(robot_speech)
                while not convo_over: 
                    self.robot_speech(robot_speech)
                    if number_of_tries > 0 : 
                        robot_speech = "Hi, I didn't get any response from you, did you say anything"
                        self.robot_speech(robot_speech)
                    if number_of_tries > 3 :
                        convo_over = True
                    try : 
                        human_speech =  rospy.wait_for_message('/to_robot'  , String , timeout=2.0)
                    except : 
                        number_of_tries = number_of_tries + 1
                        # human_speech ="Sure, I will move aside"
                        human_speech = "Sorry, I need to pass, in a hurry"
                    self.human_speech(human_speech)
                    rospy.loginfo(self.dialogue_history)
                    response  = listener_convo(self.dialogue_history)
                    rospy.loginfo(response)
                    if response['mode'] != '':
                        convo_over = True

                        if 'back' in response['mode']: 
                            print('---------------------backing off robot -------------------')
                            rospy.set_param('/back_off/robot' , True)
                         
                print('-------SCENARIO FINISHED------')
                rospy.set_param('start_convo' , False) 
            except : 
                pass

    def human_speech_cb(self,  data):
        if rospy.get_param('robot_is_listening' , True)  :
            self.convo_started_by_human = True 
            human_text = data.data
            self.human_speech(human_text)
            response = listener_convo(self.dialogue_history)
            if response['speak_to_human'] :
                self.robot_speaker(response['speech'])
            if 'back' in response['mode']  :
                rospy.set_param('back_off/robot' , True)
            else : 
                pass
            rospy.set_param('robot_spoken' , True)

    def attr_cb(self , data)  :
        pass

if __name__ == "__main__" :
    rospy.init_node('robot_llm_node_1' )
    obj = robot_node()
    rospy.spin()