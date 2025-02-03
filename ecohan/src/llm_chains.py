from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel , Field
from langchain_ollama import OllamaLLM
import yaml
import rospkg
import rospy

ros_pack = rospkg.RosPack()

llm_config_file = ros_pack.get_path('ecohan') +'/config/conversation.yaml'
# print(llm_config_file)
 
with open(llm_config_file, 'r') as f: 
    llm_config = yaml.safe_load(f)
# print(llm_config)
# except :
    # print('LLM Config File Missing !!')

model = OllamaLLM(model=rospy.get_param('llm_model' , default ='llama3.2') , 
                  temperature=rospy.get_param('llm_temperature' , default=0.1), 
                  base_url = rospy.get_param('llm_base_url' , 'http://shinigami:11111'))

class robot_listener_output(BaseModel):
    speak_to_human : bool = Field(description="set to true if there is a need for speaking with human" , default=True)
    output : str = Field(description="the sentence, the robot needs to speak to the human")
    mode : str  = Field(description="The navigation mode the robot needs to switch to  (back_off , move_forward)" , default="back_off")

listener_prompt = PromptTemplate.from_template(llm_config['conversation_robot_listener']['task'])
# print(listener_prompt)
listener_output = llm_config['conversation_robot_listener']['output_format']
listener_output_parser = JsonOutputParser(pydantic_object=robot_listener_output)
listener_chain = listener_prompt | model | listener_output_parser

def listener_convo(input):
    response = listener_chain.invoke({
        'conversation_history' : input, 
        'output_format' : listener_output
        })
    return response



class robot_convo_output(BaseModel):
    output : str = Field(description="the sentence, the robot needs to speak to the human")


attr_prompt = PromptTemplate.from_template(llm_config['attr_convo_speaker']['task'])
attr_output = llm_config['attr_convo_speaker']['output_format']
attr_output_parser = JsonOutputParser(pydantic_object=robot_convo_output)
attr_chain = attr_prompt | model | attr_output_parser

def attr_convo(input) : 
    response = attr_chain.invoke({
        'time_of_nearest_position' : input[0],
        'distance_of_closest_encounter' : input[1],
        'direction_of_crossing' : input[2]
    })
    return response
