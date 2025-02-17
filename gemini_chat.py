import google.generativeai as genai

# Set up your API key
API_KEY = "AIzaSyD2ArK74wBtL1ufYmpyrV2LqaOBrSi3mlU"
genai.configure(api_key=API_KEY)

# Create a function to send prompts to Gemini API
def get_gemini_response(prompt):
    model = genai.GenerativeModel("gemini-pro")  # Choose the Gemini model
    response = model.generate_content(prompt)
    return response.text

if __name__ == "__main__":
    print("Welcome to the Gemini Chatbot! Type 'exit' to end the chat.")
    while True:
        user_prompt = input("You: ")
        if user_prompt.lower() == "exit":
            print("Chatbot: Goodbye!")
            break
        response = get_gemini_response(user_prompt)
        print("Chatbot:", response)
