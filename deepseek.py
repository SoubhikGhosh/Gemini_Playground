import subprocess
import re
from threading import Thread
from queue import Queue, Empty

class Chatbot:
    def __init__(self, model_name="deepseek-r1:14b"):
        self.model_name = model_name
        self.process = None
        self.history = []
        self.response_queue = Queue()
        self.error_queue = Queue()
        self.running = False

    def start_session(self):
        """Starts the Ollama session with proper error handling"""
        try:
            self.process = subprocess.Popen(
                ["ollama", "run", self.model_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
            self.running = True
            
            # Start separate threads for reading stdout and stderr
            Thread(target=self._read_output, daemon=True).start()
            Thread(target=self._read_errors, daemon=True).start()
            
        except Exception as e:
            raise RuntimeError(f"Failed to start session: {str(e)}")

    def _read_output(self):
        """Continuously read from stdout and buffer responses"""
        while self.running:
            line = self.process.stdout.readline()
            if line:
                # Remove <think> tags using regex
                cleaned_line = re.sub(r'<think>.*?</think>', '', line, flags=re.DOTALL)
                self.response_queue.put(cleaned_line.strip())
            else:
                self.running = False

    def _read_errors(self):
        """Continuously read from stderr"""
        while self.running:
            line = self.process.stderr.readline()
            if line:
                self.error_queue.put(line.strip())
            else:
                self.running = False

    def ask(self, prompt, timeout=10):
        """Send prompt and return complete response"""
        if not self.running:
            raise RuntimeError("Session is not active")
            
        # Add to conversation history
        self.history.append(f"You: {prompt}")
        
        try:
            # Send prompt with newline
            self.process.stdin.write(prompt + "\n")
            self.process.stdin.flush()
        except Exception as e:
            raise RuntimeError(f"Failed to send prompt: {str(e)}")

        # Collect response lines
        response = []
        end_marker = ">>>"  # Ollama's prompt marker
        
        try:
            while True:
                try:
                    chunk = self.response_queue.get(timeout=timeout)
                    if end_marker in chunk:
                        chunk = chunk.replace(end_marker, "").strip()
                        if chunk:  # Add final chunk before marker
                            response.append(chunk)
                        break
                    response.append(chunk)
                except Empty:
                    raise TimeoutError("Response timed out")
        except Exception as e:
            self.close_session()
            raise RuntimeError(f"Error receiving response: {str(e)}")

        # Check for errors
        if not self.error_queue.empty():
            error = "\n".join(iter(self.error_queue.get, None))
            raise RuntimeError(f"Model error: {error}")

        full_response = "\n".join(response).strip()
        self.history.append(f"Bot: {full_response}")
        return full_response

    def close_session(self):
        """Properly clean up resources"""
        if self.process and self.running:
            self.running = False
            try:
                self.process.stdin.close()
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                self.process.kill()
            finally:
                self.process = None
        self.history.clear()

def start_chat():
    bot = Chatbot()
    try:
        bot.start_session()
        print("Chatbot started. Type 'exit' to end the session.")
        print("Conversation history will be maintained during the session.")
        print("<think> tags are automatically removed from responses.\n")
        
        while True:
            try:
                user_input = input("You: ")
                if user_input.lower() == 'exit':
                    break
                
                response = bot.ask(user_input)
                print(f"Bot: {response}")
                
            except KeyboardInterrupt:
                print("\nSession interrupted by user")
                break
            except Exception as e:
                print(f"Error: {str(e)}")
                break
                
    finally:
        bot.close_session()
        print("\nSession ended. Conversation history cleared.")

if __name__ == "__main__":
    start_chat()