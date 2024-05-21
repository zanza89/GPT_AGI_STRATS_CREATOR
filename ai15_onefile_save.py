# pylint: disable=E0401
# this one saves the asssitant ids so that we dont have to create a new one every time.
# THIS WORKS AND MAKES IT SO IT DOESNT MAKE MORE ASSITANTS IT LOOKS IN THE ID FOLDER
import dontshareconfig as d
from openai import OpenAI
import time
import re
from datetime import datetime
import requests
from io import BytesIO
import PyPDF2
from youtube_transcript_api import YouTubeTranscriptApi
import os

client = OpenAI(api_key=d.key)
MODEL = 'gpt-4o'

def save_assistant_id(assistant_id, filename):
    filepath = f'ids/{filename}'
    directory = os.path.dirname(filepath)
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(filepath, 'w') as file:
        file.write(assistant_id)

def check_existing_assistant_id(filename):
    filepath = f'ids/{filename}'
    if os.path.exists(filepath):
        with open(filepath, 'r') as file:
            assistant_id = file.read().strip()
        if assistant_id:
            return assistant_id
    return None

def create_and_run_assistant(name, instructions, model, content, filename):
    assistant_id = check_existing_assistant_id(filename)
    if assistant_id:
        print(f"Using existing assistant with ID: {assistant_id}")
    else:
        try:
            assistant = client.beta.assistants.create(
                name=name,
                instructions=instructions,
                tools=[{"type": "code_interpreter"}],
                model=model
            )
            print(f'{name} created....')
            assistant_id = assistant.id
            save_assistant_id(assistant_id, filename)
        except Exception as e:
            print(f"An error occurred while creating the assistant: {e}")
            return None

    try:
        thread = client.beta.threads.create()
        print(f'Thread for {name} created...{thread.id}')
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role='user',
            content=content
        )

        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id,
        )
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status in ['completed', 'failed', 'cancelled']:
                print(f'Run completed with status: {run_status.status}')
                break
            else:
                print(f'{name} Developing Strategy Then Backtesting...')
                time.sleep(5)
        print(f'Run for {name} finished, fetching messages...')
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        return extract_assistant_output(messages.data)
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def generate_filename(strategy_description, extension):
    words = strategy_description.split()
    if len(words) >= 41:
        strategy_name = '_'.join(words[39:42]).lower()
    else:
        strategy_name = '_'.join(words[:2]).lower()
    timestamp = datetime.now().strftime("%m_%d_%y_%H_%M")
    return f"{strategy_name}_{timestamp}.{extension}"

def save_output_to_file(output, idea, directory, extension):
    filename = generate_filename(idea, extension)
    filepath = f'{directory}/{filename}'
    directory = os.path.dirname(filepath)
    if not os.path.exists(directory):
        os.makedirs(directory)
    try:
        with open(filepath, 'w') as file:
            file.write(output)
        print(output)
        time.sleep(5)
        print(f"Output saved to {filepath}")
    except FileNotFoundError:
        print(f"File not found: {filepath}, moving on to the next one.")

def extract_assistant_output(messages):
    output = ""
    for message in messages:
        if message.role == 'assistant' and hasattr(message.content[0], 'text'):
            output += message.content[0].text.value + "\n"
    return output.strip()

def create_and_run_data_analysis(trading_idea):
    filename = 'strategy_assistant.txt'
    data_analysis_output = create_and_run_assistant(
        name='Strategy Creator AI',
        instructions='Create a trading strategy based on the given trading idea.',
        model=MODEL,
        content=f"Create a trading strategy using {trading_idea}. The strategy should be detailed enough for another AI to code a backtest. output the instructions for the strategy, assuming that another ai will then code the backtest. so output precise instructions for the other ai to build the backtest. THE ONLY OUTPUT YOU WILL MAKE IS THE STRATEGY INSTRUCTIONS FOR THE OTHER AI WHO WILL CODE THE BACKTEST. DO NOT OUTPUT ANYTHING ELSE. DO NOT CODE",
        filename=filename
    )
    if data_analysis_output:
        filename_base = generate_filename(data_analysis_output, 'txt').split('.')[0]
        root_path = os.path.dirname(os.path.abspath(__file__))
        save_output_to_file(data_analysis_output, data_analysis_output, os.path.join(root_path, 'strategies_event'), 'txt')
        return data_analysis_output, filename_base
    else:
        print(f"No strategy output received for {trading_idea}.")
        return None, None

def create_and_run_backtest(strategy_output, trading_idea, filename_base):
    filename = 'backtest_assistant.txt'
    backtest_output = create_and_run_assistant(
        name='Backtest Coder AI',
        instructions='Code a backtest for the provided trading strategy using backtesting.py, output only the code of the backtest',
        model=MODEL,
        content=f"Strategy Output: {strategy_output}. Please use backtesting.py to code this strategy. YOUR MISSION IS TO TAKE THE STRATEGY AND CODE A BACKTEST USING BACKTEST.PY -- ONLY OUTPUT THE BACKTEST CODE",
        filename=filename
    )
    if backtest_output:
        root_path = os.path.dirname(os.path.abspath(__file__))
        save_output_to_file(backtest_output, strategy_output, os.path.join(root_path, 'bt_code_event'), 'py')
    else:
        print(f"No backtest output received for {trading_idea}.")

def get_youtube_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_generated_transcript(['en'])
        return ' '.join([t['text'] for t in transcript.fetch()])
    except Exception as e:
        print(f"Error fetching transcript: {e}")
        return None

def get_pdf_text(url):
    try:
        response = requests.get(url)
        pdf = PyPDF2.PdfReader(BytesIO(response.content))
        text = ""
        for page in range(len(pdf.pages)):
            text += pdf.pages[page].extract_text() + "\n"
        return text
    except PyPDF2.errors.PdfReadError:
        print(f"Error reading PDF from {url}")
        return None

def process_trading_ideas(ideas_list):
    for idea in ideas_list:
        print(f"Processing trading idea: {idea}")
        strategy_output, filename_base = create_and_run_data_analysis(idea)
        if strategy_output:
            create_and_run_backtest(strategy_output, idea, filename_base)

def read_trading_ideas_from_file(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file if line.strip()]

def classify_and_process_idea(idea):
    youtube_pattern = r"(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/(watch\?v=)?([a-zA-Z0-9\-_]+)"
    pdf_pattern = r"(https?:\/\/)?([\w\d]+\.)?([\w\d]+)\.(pdf)"

    youtube_match = re.match(youtube_pattern, idea)
    pdf_match = re.match(pdf_pattern, idea)

    if youtube_match:
        video_id = youtube_match.groups()[-1]
        transcript = get_youtube_transcript(video_id)
        if transcript:
            process_trading_ideas([transcript])
    elif pdf_match:
        pdf_text = get_pdf_text(idea)
        if pdf_text:
            process_trading_ideas([pdf_text])
    else:
        process_trading_ideas([idea])

def main_idea_processor(file_path):
    global run_counter
    with open(file_path, 'r') as file:
        ideas = [line.strip() for line in file.readlines() if line.strip()]
    for idea in ideas:
        run_counter += 1
        print(f"Run #{run_counter} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Processing trading idea: {idea}")
        classify_and_process_idea(idea)

run_counter = 0
main_idea_processor('strat_ideas.txt')
