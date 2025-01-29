#! /usr/bin/env python
import rospy
from std_msgs.msg import String

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel , Field
from langchain_ollama import OllamaLLM
import yaml
import rospkg
import time
from rosgraph_msgs.msg import Clock

ros_pack = rospkg.RosPack()





class robot_listener_output(BaseModel):
    speak_to_human : bool = Field(description="set to true if there is a need for speaking with human" , default=True)
    output : str = Field(description="the sentence, the robot needs to speak to the human")
    mode : str  = Field(description="The navigation mode the robot needs to switch to  (back_off , move_forward)" , default="back_off")


class proactive_robot_output(BaseModel):
    pass 

class attr_to_text_output(BaseModel):
    


class robot_node:
    def __init__(self)  :
        config_location  = ros_pack.get_path('ecohan')  + '/config/conversation.yaml'
        with open(config_location , 'r' ) as f :
            yaml_data = yaml.safe_load(f) 
        parser = JsonOutputParser(pydantic_object=robot_listener_output)
        task= yaml_data['conversation_robot_start']['task']
        prompt = PromptTemplate.from_template(task )
        model = OllamaLLM(model = 'llama3.2' ,  temperature=0.1 , base_url='http://shinigami:11111')
        self.output_format = yaml_data['conversation_robot_start']['output_format']
        self.chain = prompt | model | parser  
        self.proactive_dialogue_history = []
        rospy.set_param('robot_is_listening' , True)
        self.proactive_chain =  prompt  | model | parser # TODO: update the prompt and the parser
        rospy.Subscriber('/to_robot' , String  , self.human_speech_cb)
        # rospy.Subscriber('/cohan_attr/full_text' , String , self.attr_cb)
        rospy.Subscriber('/clock' , Clock ,  self.proactive_cb )
    
    def robot_speaker(self , statement):
        print(statement)
        self.proactive_dialogue_history.append('robot said  : ' + str(statement))
        #TODO: Put up some TTS calls here

    def proactive_cb(self , _ ):
        if rospy.get_param('start_convo') and  (not self.convo_started_by_human) : 
            rospy.set_param('robot_is_listening' , False)
            number_of_tries = 0
            self.proactive_dialogue_history = []
            convo_over = False
            robot_speech = rospy.wait_for_message('/cohan_attr/full_text' , String  , timeout= 1.0) # TODO: Remove the full_text and get attributes from attr.py
            #TODO: Convert the attributes to speech with LLM
            while not convo_over: 
                self.robot_speaker(robot_speech)
                if number_of_tries > 0 : 
                    robot_speech = "Hi, I didn't get any response from you, did you say anything"
                    self.robot_speaker(robot_speech)
                if number_of_tries > 3 :
                    convo_over = True
                try : 
                    human_speech =  rospy.wait_for_message('/to_robot'  , String , timeout=4.0)
                except : 
                    number_of_tries = number_of_tries + 1
                self.proactive_dialogue_history.append('human said : '  + str(human_speech) )
                response  = self.proactive_chain.invoke({'dialogue_history' : self.proactive_dialogue_history})
                if response['convo_over']  :
                    if 'back' in response['conclusion']: 
                        rospy.set_param('/back_off/robot' , True) 



    def human_speech_cb(self,  data):
        if rospy.get_param('robot_is_listening' , True)  :
            human_speech =  data.data
            print(human_speech)
            response = self.chain.invoke({'human_speech' :  human_speech,
                               'output_format': self.output_format
                               })
            print(response)
            if response['speak_to_human'] :
                self.convo_started_by_human = True 
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