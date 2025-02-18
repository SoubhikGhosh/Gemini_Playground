import subprocess

class Chatbot:
    def __init__(self, model_name="deepseek-r1:14b"):
        self.model_name = model_name
        self.process = None

    def start_session(self):
        """Starts the Ollama session and keeps it alive."""
        try:
            # Start the session with the specified model
            self.process = subprocess.Popen(
                ["ollama", "run", self.model_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'  # Handle encoding to prevent unicode issues
            )
        except Exception as e:
            raise Exception(f"Failed to start the session: {e}")

    def ask(self, prompt):
        """Sends a prompt to the running session and returns the response."""
        if not self.process:
            raise Exception("Session is not started. Call start_session() first.")

        try:
            # Send the prompt to the session via stdin
            self.process.stdin.write(prompt + "\n")
            self.process.stdin.flush()

            # Read the response from the session's stdout
            response = self.process.stdout.readline().strip()

            if not response:
                error_message = self.process.stderr.read().strip()
                raise Exception(f"Error in response: {error_message}")

            return response
        except Exception as e:
            return f"An error occurred while processing the prompt: {e}"

    def close_session(self):
        """Properly closes the session."""
        if self.process:
            self.process.stdin.close()
            self.process.stdout.close()
            self.process.stderr.close()
            self.process.terminate()
            self.process.wait()

def start_chat():
    bot = Chatbot()  # Initialize chatbot with the specific model
    try:
        bot.start_session()  # Start the session once before chatting
        print("Chatbot is ready. Type 'exit' to end the conversation.")
        
        # Chat loop
        while True:
            user_input = input("You: ")
            if user_input.lower() == 'exit':
                print("Goodbye!")
                break

            response = bot.ask(user_input)
            print(f"Bot: {response}")
    
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        bot.close_session()  # Ensure the session is closed when the chat ends

if __name__ == "__main__":
    start_chat()
