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
ros_pack = rospkg.RosPack()





class robot_listener_output(BaseModel):
    speak_to_human : bool = Field(description="set to true if there is a need for speaking with human" , default=True)
    output : str = Field(description="the sentence, the robot needs to speak to the human")
    mode : str  = Field(description="The navigation mode the robot needs to switch to  (back_off , move_forward)" , default="back_off")



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
        rospy.Subscriber('/to_robot' , String  , self.human_speech_cb)
        rospy.Subscriber('/cohan_attr/full_text' , String , self.attr_cb)

    def human_speech_cb(self,  data):
        human_speech =  data.data
        print(human_speech)
        response = self.chain.invoke({'human_speech' :  human_speech,
                           'output_format': self.output_format
                           })
        print(response)
        if response['speak_to_human'] : 
            print(response['speech'])
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