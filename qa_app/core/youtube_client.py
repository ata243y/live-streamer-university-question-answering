
import logging
import pytchat
import threading
import time

logger = logging.getLogger(__name__)

class YouTubeClient:
    def __init__(self):
        self.chat = None
        self.is_listening = False
        self.listener_thread = None

    def start_listening(self, video_id, callback):
        """
        Starts listening to the YouTube live chat.
        :param video_id: The video ID of the live stream.
        :param callback: A function to call when a question is received. 
                         Signature: callback(author_name, message_text)
        """
        if self.is_listening:
            logger.warning("Already listening to a stream.")
            return

        try:
            self.chat = pytchat.create(video_id=video_id)
            self.is_listening = True
            
            def _listen():
                logger.info(f"Started listening to YouTube chat for video: {video_id}")
                while self.is_listening and self.chat.is_alive():
                    try:
                        for c in self.chat.get().sync_items():
                            message = c.message
                            author = c.author.name
                            logger.debug(f"Chat: {author}: {message}")
                            
                            # Simple filter for questions
                            if '?' in message:
                                logger.info(f"Question detected from {author}: {message}")
                                callback(author, message)
                                
                    except Exception as e:
                        logger.error(f"Error in chat listener: {e}")
                    
                    time.sleep(1) # Poll every second
                
                logger.info("Stopped listening to YouTube chat.")

            self.listener_thread = threading.Thread(target=_listen, daemon=True)
            self.listener_thread.start()

        except Exception as e:
            logger.error(f"Failed to start YouTube listener: {e}")
            self.is_listening = False

    def stop_listening(self):
        self.is_listening = False
        if self.chat:
            self.chat.terminate()
            self.chat = None
