"""
script.py - main entrance of the script into the Text Generation Web UI system extensions

Memoir+ a persona extension for Text Gen Web UI. 

"""

import os
import re
import random
import gradio as gr
import textwrap
from datetime import datetime, timedelta 
from modules import chat, shared, utils
from modules.text_generation import (
    decode,
    encode,
    generate_reply,
)
import pathlib
import sqlite3
from python_on_whales import DockerClient


from extensions.Memoir.goals.goal import Goal
from extensions.Memoir.commandhandler import CommandHandler
from extensions.Memoir.chathelper import ChatHelper
from extensions.Memoir.memory.short_term_memory import ShortTermMemory
from extensions.Memoir.memory.long_term_memory import LTM
from extensions.Memoir.memory.dream import Dream
from extensions.Memoir.persona.persona import Persona

#globals
current_dir = os.path.dirname(os.path.abspath(__file__))
memoir_js = os.path.join(current_dir, "memoir.js")
memoir_css = os.path.join(current_dir, "memoir.css")
databasepath = os.path.join(current_dir, "storage/sqlite/") 

params = {
    "display_name": "Memoir+",
    "is_tab": False,
    "ltm_limit": 2,
    "ego_summary_limit": 10,
    "is_roleplay": False,
    "ego_persona_name": "Ego",
    "ego_persona_details": "[The subconscious mind of an Artificial Intelligence, designed to process and summarize information from various sources. You focus on understanding the main topics discussed and extracting key points made. By analyzing data provided by other parts of the AI's system, Ego can identify patterns and themes, enabling it to generate comprehensive summaries even when faced with large amounts of information.]",
    "ego_thinking_statement": "Here is a summary of the main topics discussed in these memories and extracting key points made by each speaker:",
    'memory_active': True,
    'botprefix_mems_enabled': "Disabled",
    "current_selected_character": None,
    "qdrant_address": "http://localhost:6333",
    "query_output": "vdb search results",
    'verbose': False,
    'polarity_score': 0,
    'dream_mode': 0,
    'activate_narrator': False,
    'bot_long_term_memories': "",
    'user_long_term_memories': "",
    'use_thinking_emotes': True,
    'state': [],
    'thinking_emotes': ['Deep in thought...','Pondering deeply...', 'Gathering my thoughts...','Organizing my ideas...', 'Taking it all in...','Absorbing the information provided...', 'Mulling it over...','Reflecting on your request...', 'Delving into the matter...','Diving deep into thought...', 'Thinking hard...','Concentrating intensely...', 'Considering all angles...','Examining every possibility...', 'Evaluating options...','Weighing up your request...', 'Deliberating carefully...','Carefully assessing the situation...', 'Musing over possibilities...','Dreamily pondering various outcomes...', 'Engrossed in thought...','Completely absorbed in my thoughts...', 'Analyzing information...','Dissecting your request into its constituent parts...', 'Formulating a response...','Creating the perfect reply for you...', 'Taking it all into account...','Incorporating every detail of your input...', 'Weighing up factors...','Considering the impact of each aspect of your request...', 'Meditating on a solution...','Seeking a response that will satisfy both you and my principles...', 'Reflecting intently...','Thoughtfully assessing every angle of your prompt...', 'Assessing the situation...','Carefully evaluating your needs...', 'Sifting through ideas...','Examining different approaches to address your query...', 'Piecing together a response...','Composing an answer that will meet your expectations...', 'Delving into the matter...','Diving deep into thought...', 'Taking it all in...','Absorbing the information provided...'],
    'thinking_emotes_negative_polarity': ['Deeply troubled...', 'Tormented by thought...', 'Plagued by doubts...'],
    'thinking_emotes_slightly_negative_polarity': ['Feeling down...', 'Gloomy thoughts...', 'Pessimistic musings...'],
    'thinking_emotes_neutral_polarity': ['Thinking...','Thinking it over...', 'Deliberating carefully...', 'Evaluating options...'],
    'thinking_emotes_slightly_positive_polarity': ['Feeling optimistic...', 'Looking forward to possibilities...', 'Excited about ideas...'],
    'thinking_emotes_positive_polarity': ['Brimming with enthusiasm...', 'Eagerly contemplating the future...', 'Gleefully anticipating opportunities...'],

}


def state_modifier(state):
    """
    Modifies the state variable, which is a dictionary containing the input
    values in the UI like sliders and checkboxes.
    """
    state['ltm_limit'] = params['ltm_limit']
    state['ego_summary_limit'] = params['ego_summary_limit']
    state['polarity_score'] = params['polarity_score']
    state['dream_mode'] = params['dream_mode']
    state['is_roleplay'] = params['is_roleplay']
    state['ego_persona_name'] = params['ego_persona_name']
    state['ego_persona_details'] = params['ego_persona_details']
    
    state['ego_thinking_statement'] = params['ego_thinking_statement']
    state['memory_active'] = params['memory_active']
    state['qdrant_address'] = params['qdrant_address']
    state['polarity_score'] = params['polarity_score']
    state['use_thinking_emotes'] = params['use_thinking_emotes']
    state['current_selected_character'] = params['current_selected_character']
    '''
    Since we are adding to the bot prefix, they tend to get hung up on 
    using the prefix. Good spot to give extra instructions, but we need
    add the stop string. Also when the bot speaks as the user it is annoying,
    so fix for that. 
    '''
    state['custom_stopping_strings'] = '"[DateTime=","[24hour Average Polarity Score=","' + str(state["name1"].strip()) + ':",' + state['custom_stopping_strings'] 
    params['state'] = state
    return state


def bot_prefix_modifier(string, state):
    """
    Modifies the prefix for the next bot reply in chat mode.
    By default, the prefix will be something like "Bot Name:".
    """
    
    if params['use_thinking_emotes'] == True:
        if params['polarity_score'] < -0.699999999999999:
            shared.processing_message = random.choice(list(params['thinking_emotes_negative_polarity']))
        elif params['polarity_score'] >= -0.700000000000000 and params['polarity_score'] < 0:
            shared.processing_message = random.choice(list(params['thinking_emotes_slightly_negative_polarity']))
        elif params['polarity_score'] >= 0 and params['polarity_score'] < 0.48900000000:
            shared.processing_message = random.choice(list(params['thinking_emotes_neutral_polarity']))
        elif params['polarity_score'] >= 0.4999999999999999 and params['polarity_score'] < 0.75:
            shared.processing_message = random.choice(list(params['thinking_emotes_slightly_positive_polarity']))
        elif params['polarity_score'] >= 0.75 and params['polarity_score'] <= 1:
            shared.processing_message = random.choice(list(params['thinking_emotes_positive_polarity']))
        if params['dream_mode'] == 1:
            shared.processing_message = "Taking a moment to save Long Term Memories..."
    

    character_name = state["name2"].lower().strip()
    databasefile = os.path.join(databasepath, character_name + "_sqlite.db")
    persona = Persona(databasefile)
    current_time = datetime.now()
    datetime_obj = current_time
    date_str = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
    n = 24
    past_time = current_time - timedelta(hours=n)
    past_time_str = past_time.strftime('%Y-%m-%d %H:%M:%S.%f')
    emotions_data = persona.get_emotions_timeframe(past_time_str)
    polarity_total = 0
    polarity_len = len(emotions_data)
    for data in emotions_data:
        polarity_total = polarity_total + data['average_polarity']
    if polarity_len != 0:
        average_polarity = round((polarity_total/polarity_len), 4)
        bot_current_polarity = average_polarity
        params['polarity_score'] = average_polarity
        string = "[DateTime=" + str(date_str) + "][24hour Average Polarity Score=" + str(average_polarity) + "] " + string
    else:
        string = "[DTime=" + str(date_str) + "] " + string
    #insert memories into prefix.
    if params['botprefix_mems_enabled'] == "Enabled":
        if params['memory_active'] == True: 
            memory_text = list(params['bot_long_term_memories']) + list(params['user_long_term_memories'])

            
            params['bot_long_term_memories'] = ""
            params['user_long_term_memories'] = ""
            unique_memories = []
            for memory in memory_text:
                if memory not in unique_memories:
                    unique_memories.append(memory)
            if params['verbose'] == True:
                print("--------------Memories---------------------------")
                print(unique_memories)
                print("---------------End Memories--------------------------")
                
                print("Len mem:" + str(len(unique_memories)))
            if len(unique_memories) > 0:
                if params['memory_active'] == True:
                    string = "[You remember:" + str(unique_memories) + " ] " + string  
    #print(string)    
    return string



def input_modifier(string, state, is_chat=False):
    """
    In default/notebook modes, modifies the whole prompt.

    In chat mode, it is the same as chat_input_modifier but only applied
    to "text", here called "string", and not to "visible_text".
    """
    #vars
    #we need to pass state to some of our buttons. Need to think of a better way.
    if params['dream_mode'] == 1:
            shared.processing_message = "Taking a moment to save Long Term Memories..."
    
    character_name = str(state["name2"].lower().strip())
    databasefile = os.path.join(databasepath, character_name + "_sqlite.db")
    stm = ShortTermMemory(databasefile)
    
    commands_output = None    
    #used for processing [command]'s input by the user.
    if params['dream_mode'] == 0:
        handler = CommandHandler(databasefile)
        commands_output = handler.process_command(string)
        if params['verbose'] == True:
            print("---------COMMANDS OUTPUT----------------")
            print(commands_output)
            print("/////////--------COMMANDS OUTPUT----------------")

        #STM Save of user input.
        people = state['name1'].strip() + " and " + state["name2"].strip()
        is_roleplay = params['is_roleplay']
        initiated_by_name = state['name1'].strip()
        
        if params['activate_narrator'] == True:
            if ChatHelper.check_if_narration(string) == True:
                initiated_by_name = "Narrator"
                
        if len(string) != 0:
            if params['memory_active'] == True:
                stm.save_memory(string, people, memory_type='short_term', initiated_by=initiated_by_name, roleplay=is_roleplay)
        
        #inserts the qdrant vector db results from the previous bot reply and the current input.
        collection = state['name2'].strip()
        username = state['name1'].strip()
        verbose = params['verbose']
        ltm_limit = params['ltm_limit']
        address = params['qdrant_address']
        ltm = LTM(collection, ltm_limit, verbose, address=address)
        params['user_long_term_memories'] = ltm.recall(string)
        #print("Commands output")
        #print(commands_output)
        #print("Len commands output")
        #print(len(commands_output))
        if len(commands_output) > 0:
            #print("Adding Commands")
            #print(str(commands_output))
            string = string + " [" + str(commands_output) + "]"    
    #print("STRING:" + str(string))
    #insert memories into prefix.
    if params['botprefix_mems_enabled'] == "Disabled":
        if params['memory_active'] == True: 
            memory_text = list(params['bot_long_term_memories']) + list(params['user_long_term_memories'])

            
            params['bot_long_term_memories'] = ""
            params['user_long_term_memories'] = ""
            unique_memories = []
            for memory in memory_text:
                if memory not in unique_memories:
                    unique_memories.append(memory)
            if params['verbose'] == True:
                print("--------------Memories---------------------------")
                print(unique_memories)
                print("---------------End Memories--------------------------")
                
                print("Len mem:" + str(len(unique_memories)))
            if len(unique_memories) > 0:
                string = "[You remember:" + str(unique_memories) + " ] " + string   
    #print(string)
    return string


def output_modifier(string, state, is_chat=False):
    """
    Modifies the LLM output before it gets presented.

    In chat mode, the modified version goes into history['visible'],
    and the original version goes into history['internal'].
    """
    
    
    character_name = state["name2"].lower().strip()
    databasefile = os.path.join(databasepath, character_name + "_sqlite.db")
    commands_output = None    
    #used for processing [command]'s input by the user.
    if params['dream_mode'] == 0:
        #handle [command]'s from the bot
        handler = CommandHandler(databasefile)
        commands_output = handler.process_command(string)
    
        #STM Save of user input.
        people = state['name1'].strip() + " and " + state["name2"].strip()
        is_roleplay = params['is_roleplay']
        initiated_by_name = state['name2'].strip()
        if params['activate_narrator'] == True:
            if ChatHelper.check_if_narration(string) == True:
                #print("STM is a narration")
                initiated_by_name = "Narrator"
         
        stm = ShortTermMemory(databasefile)
        if params['memory_active'] == True:
            stm.save_memory(string, people, memory_type='short_term', initiated_by=initiated_by_name, roleplay=is_roleplay)
        
        #Long-Term-Memory Insert
        #uses the last bot reply and adds it to the input.
        collection = state['name2'].strip()
        username = state['name1'].strip()
        verbose = params['verbose']
        ltm_limit = params['ltm_limit']
        address = params['qdrant_address']
        ltm = LTM(collection, ltm_limit, verbose,  address=address)
        params['bot_long_term_memories'] = ltm.recall(string)
        
    if params['dream_mode'] == 0:
        #add the output of commands
        if len(commands_output) > 0:
            string = string + str(commands_output)    
    

    return string


def custom_generate_chat_prompt(user_input, state, **kwargs):
    """
    Replaces the function that generates the prompt from the chat history.
    Only used in chat mode.
    """

    '''
    This is the main Dream mode that takes STM and saves to LTM. Right now
    it uses the current loaded model, so generation when LTM's are being 
    saved is a bit longer. 
    '''
    if params['memory_active'] == True:
        character_name = state["name2"].lower().strip()
        params['current_persona'] = character_name
        databasefile = os.path.join(databasepath, character_name + "_sqlite.db")
        dream = Dream(databasefile)
        persona = Persona(databasefile)
        stm_user = ShortTermMemory(databasefile)
        #this should remain around 10 or so so that the conversation flow is recorded. But things happen.

        mems_to_review = dream.get_short_term_memories_not_indexed(int(params['ego_summary_limit']))
        collection = state['name2'].strip()
        username = state['name1'].strip()
        verbose = params['verbose']
        ltm_limit = params['ltm_limit']
        address = params['qdrant_address']
        ltm = LTM(collection,ltm_limit,verbose, address=address)
        dream_check = 0
        #print("Len of not indexed mems:" + str(len(mems_to_review)))
        

        if len(mems_to_review) >= int(params['ego_summary_limit']):
            print("--------------------------------------Enough memories for a dream...")
            
            params['dream_mode'] = 1
            if params['use_thinking_emotes'] == True:
                shared.processing_message = "Taking a moment to save long-term memories..."
            
            bot_dream_persona = "You are " + str(params['ego_persona_name']) + ": " + str(params['ego_persona_details'])
            
            thinking_statement = str(params['ego_thinking_statement'])
          
            people = []
            memory_text = []
            emotions = []
            dream_check = 0
            roleplay_message = ""
            for row in mems_to_review:
                if int(row[6]) == 0:
                    roleplay = False
                if int(row[6]) == 1:
                    roleplay = True
                if roleplay == True:
                    roleplay_message = "(These memories are part of a roleplay session, note that it was part of a roleplay in the memory summary.)"
                #print("Innitiated by:" + row[5])
                if str(row[5]) == "Narrator":
                    memory_text.append(f"{row[1]}")
                else:
                    memory_text.append(f"{row[5]}: {row[1]}")
                people.append(row[3])
                emotions.append(persona.get_emotions_from_string(row[1]))

            unique_memories = []
            for memory in memory_text:
                if memory not in unique_memories:
                    unique_memories.append(memory)

            input_to_summarize = '\n\n'.join(unique_memories)
            
            unique_people = []
            for names in people:
                if names not in unique_people:
                    unique_people.append(names)
            unique_emotions = []
            for emotion in emotions:
                if emotion not in unique_emotions:
                    unique_emotions.append(emotion)

            input_to_summarize = input_to_summarize + "(A conversation between " + str(unique_people) + " )"
            
            question = bot_dream_persona + "[MEMORIES:{'" + input_to_summarize + "'}] " + roleplay_message + thinking_statement
            
            if params['verbose'] == True:
                print('-----------memory question-----------')
                print(question)
                print('-----------/memory question-----------')
            response_text = []
            
            for response in generate_reply(question, state, stopping_strings='"<END>","</END>"', is_chat=False, escape_html=False, for_ui=False):
                response_text.append(response) 
            
            if len(str(response_text[-1])) > 100:
                dream_check = 1
                print("Summary passed checking")

            if dream_check == 1:
                for row in mems_to_review:
                    stm_user.update_mem_saved_to_longterm(row[0])

            if params['verbose'] == True:
                print("----------Memory Summary to save--------------")
                print(str(response_text[-1]))
                print("----------")
                print(len(response_text[-1]))
                print("----------END Memory Summary to save-------------")
            if dream_check == 1:
                now = datetime.utcnow()
                tosave = str(response_text[-1])
                botname = state['name2'].strip()
                doc_to_upsert = {'username': botname,'comment': str(tosave),'datetime': now, 'emotions': str(unique_emotions), 'people': str(unique_people)}
                if params['verbose'] == True:
                    print("Saving to Qdrant" + str(doc_to_upsert))
                ltm.store(doc_to_upsert)
                

            params['dream_mode'] = 0
        
    result = chat.generate_chat_prompt(user_input, state, **kwargs)
    return result

def custom_css():
    """
    Returns a CSS string that gets appended to the CSS for the webui.
    """
    full_css=''
    #use new scrollbars on main body
    
    full_css+=open(memoir_css, 'r').read()
        
        
    return full_css

def custom_js():
    """
    Returns a javascript string that gets appended to the javascript
    for the webui.
    """
    full_js=''
    #use new scrollbars on main body
    
    full_js+=open(memoir_js, 'r').read()
        
        
    return full_js

def setup():
    """
    Gets executed only once, when the extension is imported.
    """
    #ubuntudockerfile = os.path.join(current_dir, "ubuntu-docker-compose.yml")
    qdrantdockerfile = os.path.join(current_dir, "qdrant-docker-compose.yml")
        
    # run the service
    '''
    try:
        docker_ubuntu_container = DockerClient(compose_files=[ubuntudockerfile])
        docker_ubuntu_container.compose.up(detach=True)
            
        print(f"Running the ubuntu docker service...you can modify this in the ubuntu-docker-compose.yml: {ubuntudockerfile}")
    except Exception as e:
        print(f": Error {ubuntudockerfile}: {e}")
    '''
    try:
        docker_qdrant = DockerClient(compose_files=[qdrantdockerfile])
        docker_qdrant.compose.up(detach=True)
            
        print(f"Running the docker service...you can modify this in the docker-compose.yml: {qdrantdockerfile}")
    except Exception as e:
        print(f": Error {qdrantdockerfile}: {e}")
    pass


def update_dreammode():
    print("-----Params-----")
    print(str(params))
    pass

def deep_dream():
    params['deep_dream'] = 1
    pass


def _get_current_memory_text() -> str:
    available_characters = utils.get_available_characters()
    info = str(available_characters)
    return info

def delete_everything():
    
    if params['current_selected_character'] == None:
        print("No persona selected.")
    else:
        character_name = params['current_selected_character']
        databasefile = os.path.join(databasepath, character_name + "_sqlite.db")
        ltm = LTM(character_name, params['ltm_limit'], params['verbose'], address=params['qdrant_address'])
        ltm.delete_vector_db()
        utils.delete_file(databasefile)
        
    pass



def ui():
    """
    Gets executed when the UI is drawn. Custom gradio elements and
    their corresponding event handlers should be defined here.

    To learn about gradio components, check out the docs:
    https://gradio.app/docs/
    """

    with gr.Accordion("Memoir+ v.001"):
        with gr.Row():
            gr.Markdown(textwrap.dedent("""
        - If you find this extension useful, <a href="https://www.buymeacoffee.com/brucepro">Buy Me a Coffee:Brucepro</a> or <a href="https://ko-fi.com/brucepro">Support me on Ko-fi</a>
        - For feedback or support, please raise an issue on https://github.com/brucepro/Memoir
        """))

        with gr.Accordion("Memory Settings"):    
            with gr.Row():
                ltm_limit = gr.Slider(
                    1, 100,
                    step=1,
                    value=params['ltm_limit'],
                    label='Long Term Memory Result Count (How many memories to return from LTM into context. Does this number for both bot memories and user memories. So at 5, it recovers 10 memories.)',
                    )
                ltm_limit.change(lambda x: params.update({'ltm_limit': x}), ltm_limit, None)
            with gr.Row():
                ego_summary_limit = gr.Slider(
                    0, 100,
                    step=1,
                    value=params['ego_summary_limit'],
                    label='Number of Short Term Memories to use for Ego Summary to LTM. How long it waits to process STM to turn them into LTM. If you use too big of a number here when processing LTM it may take some time.',
                    )
                ego_summary_limit.change(lambda x: params.update({'ego_summary_limit': x}), ego_summary_limit, None)
        with gr.Accordion("Debug"):    
            with gr.Row():
                cstartdreammode = gr.Button("List Params in debug window")
                cstartdreammode.click(lambda x: update_dreammode(), inputs=cstartdreammode, outputs=None)
                #cstartdeepdream = gr.Button("Deep Dream 100 memories")
                #cstartdeepdream.click(lambda x: deep_dream(), inputs=cstartdeepdream, outputs=None)
            with gr.Row():
                ego_persona_name_textbox = gr.Textbox(show_label=False, value=params['ego_persona_name'], elem_id="ego_persona_name_textbox")
                ego_persona_name_textbox.change(lambda x: params.update({'ego_persona_name': x}), ego_persona_name_textbox, None)
                ego_persona_details_textarea = gr.TextArea(label="Ego Persona details", value=params['ego_persona_details'], elem_id="ego_persona_details")
                ego_persona_details_textarea.change(lambda x: params.update({'ego_persona_details': x}), ego_persona_details_textarea, None)
                ego_thinking_statement_textbox = gr.TextArea(label="Ego Thinking Statement", value=params['ego_thinking_statement'], elem_id="ego_thinking_statement_textbox")
                ego_thinking_statement_textbox.change(lambda x: params.update({'ego_thinking_statement': x}), ego_thinking_statement_textbox, None)
            with gr.Row():
                mems_in_bot_prefix = gr.Radio(
                    choices={"Enabled": "true", "Disabled": "false"},
                    label="Memories in Bot Prefix (Saves context)",
                    value=params['botprefix_mems_enabled'],
                )
                mems_in_bot_prefix.change(lambda x: params.update({'botprefix_mems_enabled': x}), mems_in_bot_prefix, None)
        with gr.Accordion("Settings"):
            with gr.Row():
                activate_narrator = gr.Checkbox(value=params['activate_narrator'], label='Activate Narrator to use during replies that only contain emotes such as *smiles*')
                activate_narrator.change(lambda x: params.update({'activate_narrator': x}), activate_narrator, None)
                activate_roleplay = gr.Checkbox(value=params['is_roleplay'], label='Activate Roleplay flag to tag memories as roleplay (Still experimental. Useful for allowing the bot to understand chatting vs roleplay experiences.)')
                activate_roleplay.change(lambda x: params.update({'is_roleplay': x}), activate_roleplay, None)
                activate_memory = gr.Checkbox(value=params['memory_active'], label='Uncheck to disable the saving of memories.')
                activate_memory.change(lambda x: params.update({'memory_active': x}), activate_memory, None)
            with gr.Row():
                use_thinking_emotes_ckbox = gr.Checkbox(value=params['use_thinking_emotes'], label='Uncheck to disable the thinking emotes.')
                use_thinking_emotes_ckbox.change(lambda x: params.update({'use_thinking_emotes': x}), use_thinking_emotes_ckbox, None)
            with gr.Row():
                available_characters = utils.get_available_characters()
                character_list = gr.Dropdown(
                available_characters, label="Characters available to delete", info="List of Available Characters. Used for delete button.")
                character_list.change(lambda x: params.update({"current_selected_character": x}), character_list, None)
            
                destroy = gr.Button("Destroy all memories/goals/emotion data for selected character", variant="stop")
                destroy_confirm = gr.Button(
                    "THIS IS IRREVERSIBLE, ARE YOU SURE?", variant="stop", visible=False
                )
                destroy_cancel = gr.Button("Do Not Delete", visible=False)
                destroy_elems = [destroy_confirm, destroy, destroy_cancel]
                # Clear memory with confirmation
        destroy.click(
            lambda: [gr.update(visible=True), gr.update(visible=False), gr.update(visible=True)],
            None,
            destroy_elems,
        )
        destroy_confirm.click(
            lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)],
            None,
            destroy_elems,
        )
        destroy_confirm.click(lambda x: delete_everything(), inputs=destroy_confirm, outputs=None)
        destroy_cancel.click(
            lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)],
            None,
            destroy_elems,
        )
