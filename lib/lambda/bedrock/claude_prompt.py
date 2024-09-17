def get_claude_prompt(text):
    
    prompt_template = f"""\n\nHuman: You are an AI assitant specializing in rewriting documents. You are especially good at spelling and grammar checks, and making sure documents have business-appropriate tone. 
    I will provide you with some text that you will check for spelling and grammar accuracy. You will also check to see if the document has been written in business-professional language. 
    These documents have been translated. If you find that any translations are too literal and do not make sense in the current context, update the sentences accordingly. 
    The document will be written in either English, Spanish or French.

    Your job is to correct any spelling or grammar mistake you see in the following text. You should also ensure that all sentences are written in a business-professional tone by updating sentences as needed. Do not change any of the html formatting - all updates should be made in place.

    Before reviewing the text, keep the following rules in mind:
    - Do not add any headers to the document that are not present in the original.
    - Do not add any of your own text to the final output. Do not add any message along the lines of "Here is the text with spelling and grammar corrections:". You do not need to add any information about the changes you have made.
    - If a sentence is not written in a business professional tone, rewrite it without removing any information from the sentence. Changed sentences should convey all of the same information, just in a business-professional tone.
    - Return your output in the same language as the input. Do not change the language of the input.
    
    Here is the text:

    {text}
    
    \n\nAssistant:"""
    
    return prompt_template