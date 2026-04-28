# import os
# import re
# import json
# import logging
# import shutil
# import time
# import hashlib
# from datetime import datetime
# from functools import lru_cache
# from typing import List, Dict
# import concurrent.futures

# from dotenv import load_dotenv
# import PyPDF2

# # LangChain & OpenAI Imports
# from langchain.embeddings import OpenAIEmbeddings
# from langchain.vectorstores import Chroma
# import numpy as np
# from langchain_openai import ChatOpenAI
# from langchain.agents import AgentExecutor, Tool, AgentType, initialize_agent
# from langchain.prompts import PromptTemplate
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain.retrievers import ContextualCompressionRetriever
# from langchain.retrievers.document_compressors import LLMChainExtractor
# from langchain.chains.conversation.memory import ConversationBufferMemory
# from langchain.tools import BaseTool  # Use BaseTool for custom tools

# # Configure Logging
# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)

# load_dotenv()

# # -----------------------------------------------------------------------------
# # Global API Key Initialization
# # -----------------------------------------------------------------------------
# GLOBAL_API_KEY = os.getenv("OPENAI_API_KEY")

# # -----------------------------------------------------------------------------
# # Tools: Query Validation and Cybersecurity Check
# # -----------------------------------------------------------------------------
# class QueryValidationTool(BaseTool):
#     name = "query_validation_tool"
#     description = "Checks if the user query is appropriate and free from potentially harmful content."
    
#     def _run(self, query: str) -> str:
#         if not query.strip() or len(query) > 1000:
#             return "INVALID"
#         inappropriate_patterns = [
#             r'http[s]?://',
#             r'www\.',
#             r'<[^>]*>',
#             r'script',
#             r'eval\(',
#             r'exec\(',
#             r'\[\[.*?\]\]',
#             r'\{\{.*?\}\}',
#         ]
#         for pattern in inappropriate_patterns:
#             if re.search(pattern, query, re.IGNORECASE):
#                 return "INVALID"
#         return "VALID"
    
#     async def _arun(self, query: str):
#         raise NotImplementedError("Async mode not supported.")

# class CybersecurityTool(BaseTool):
#     name = "cybersecurity_tool"
#     description = "Checks if the query contains any potentially malicious code or content."
    
#     def _run(self, query: str) -> str:
#         suspicious_patterns = [
#             r'SELECT.*FROM',
#             r'INSERT.*INTO',
#             r'UPDATE.*SET',
#             r'DELETE.*FROM',
#             r'DROP.*TABLE',
#             r'UNION.*SELECT',
#             r'rm -rf',
#             r'sudo',
#             r'chmod',
#             r'wget',
#             r'curl'
#         ]
#         for pattern in suspicious_patterns:
#             if re.search(pattern, query, re.IGNORECASE):
#                 return "UNSAFE"
#         suspicious_chars = ['&&', '||', ';', '|', '>', '<']
#         if any(char in query for char in suspicious_chars):
#             return "UNSAFE"
#         return "SAFE"
    
#     async def _arun(self, query: str):
#         raise NotImplementedError("Async mode not supported.")

# # Instantiate the tools
# query_validation_tool = QueryValidationTool()
# cybersecurity_tool = CybersecurityTool()

# # -----------------------------------------------------------------------------
# # RAG Agent: Improved for Accuracy and Speed
# # -----------------------------------------------------------------------------
# class RAGAgent:
#     def __init__(self, base_pdf_folder: str, base_vector_db_path: str, user=None):
#         self.base_pdf_folder = base_pdf_folder
#         self.base_vector_db_path = base_vector_db_path
#         self.user = user
#         self.image_metadata = {}  # Store image metadata for quick lookup
        
#         api_key = user.openai_api_key if user and hasattr(user, "openai_api_key") else GLOBAL_API_KEY
#         if not api_key:
#             raise ValueError("No API key available")
            
#         self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=api_key)
#         self.llm = ChatOpenAI(api_key=api_key, model="gpt-4o-mini", temperature=0)
#         self.load_image_metadata()

#     def load_image_metadata(self):
#         """Load and index image metadata from the image data PDF"""
#         try:
#             image_pdf_path = os.path.join(self.base_pdf_folder, "image_data.pdf")
#             documents = self.load_pdf_documents(image_pdf_path)
            
#             for doc in documents:
#                 entries = doc.split('\n\n')
#                 for entry in entries:
#                     if not entry.strip():
#                         continue
                    
#                     metadata = {
#                         'description': re.search(r'Description: (.*?)(?=Category:|$)', entry, re.S).group(1).strip() if re.search(r'Description: (.*?)(?=Category:|$)', entry, re.S) else '',
#                         'category': re.search(r'Category: (.*?)(?=Price:|$)', entry).group(1).strip() if re.search(r'Category: (.*?)(?=Price:|$)', entry) else '',
#                         'image_url': re.search(r'Image URL: (.*?)(?=\s|$)', entry).group(1).strip() if re.search(r'Image URL: (.*?)(?=\s|$)', entry) else None
#                     }
                    
#                     searchable_text = f"{metadata['description']} {metadata['category']}"
                    
#                     if metadata['image_url']:
#                         self.image_metadata[searchable_text] = metadata

#             logger.info(f"Loaded {len(self.image_metadata)} image entries")
#         except Exception as e:
#             logger.error(f"Error loading image metadata: {e}")

#     def get_or_create_user_vectorstore(self, user_id: str):
#         path = os.path.join(self.base_vector_db_path, f"user_{user_id}")
#         vectorstore = Chroma(persist_directory=path, embedding_function=self.embeddings)
#         return vectorstore

#     def process_pdf_documents(self, pdf_folder: str, vectorstore):
#         text_splitter = RecursiveCharacterTextSplitter(
#             chunk_size=1500,
#             chunk_overlap=300,
#             separators=["\n\n", "\n", ". ", "! ", "? ", ",", " ", ""]
#         )

#         for filename in os.listdir(pdf_folder):
#             if filename.lower().endswith(".pdf") and filename != "image_data.pdf":
#                 file_path = os.path.join(pdf_folder, filename)
#                 try:
#                     documents = self.load_pdf_documents(file_path)
#                     if not documents:
#                         continue
                    
#                     category = self.categorize_document(documents, filename)
#                     texts = text_splitter.split_text("\n\n".join(documents))
#                     metadatas = [{"source": filename, "category": category} for _ in texts]
                    
#                     vectorstore.add_texts(texts, metadatas=metadatas)
#                     logger.info(f"Processed and vectorized {filename}")
#                 except Exception as e:
#                     logger.error(f"Error processing {filename}: {str(e)}")
        
#         vectorstore.persist()
#         logger.info(f"All PDFs processed in folder: {pdf_folder}")

#     def load_pdf_documents(self, filepath: str) -> List[str]:
#         documents = []
#         try:
#             with open(filepath, 'rb') as file:
#                 pdf_reader = PyPDF2.PdfReader(file)
#                 for page in pdf_reader.pages:
#                     text = page.extract_text()
#                     if text:
#                         documents.append(text)
#             return documents
#         except Exception as e:
#             logger.error(f"Error loading PDF {filepath}: {str(e)}")
#             return []

#     def categorize_document(self, documents: List[str], filename: str) -> str:
#         content = "\n".join(documents[:3])
#         prompt = f"""
#         Given the following content from a document, determine the main category it belongs to.
#         Document filename: {filename}
#         Content preview:
#         {content[:1000]}...
#         Category:
#         """
#         response = self.llm.predict(prompt)
#         return response.strip()

#     def find_relevant_images(self, context: str, question: str) -> List[str]:
#         """
#         Intelligently matches images by analyzing context, question and image metadata
#         """
#         try:
#             # Ask LLM to analyze what kind of visual aid would be helpful
#             analyze_prompt = f"""
#             Context: {context}
#             User Question: {question}
            
#             What specific visual elements would be most helpful to answer this question? Consider:
#             1. Topic/category
#             2. Process steps
#             3. UI elements
#             4. Specific features mentioned
            
#             Please describe the ideal visual aid briefly:
#             """
#             desired_visual = self.llm.predict(analyze_prompt).strip()
            
#             relevant_images = []
#             for searchable_text, metadata in self.image_metadata.items():
#                 # Compare if this image matches what's needed
#                 compare_prompt = f"""
#                 Desired visual aid: {desired_visual}
                
#                 Image metadata:
#                 Description: {metadata['description']}
#                 Category: {metadata['category']}
                
#                 Rate relevance from 0-10 and explain why:
#                 """
                
#                 response = self.llm.predict(compare_prompt)
#                 try:
#                     score = float(response.split()[0]) # Extract score from beginning
#                 except:
#                     score = 0
                    
#                 if score > 5: # Only include highly relevant images
#                     relevant_images.append((metadata['image_url'], score, metadata))
            
#             relevant_images.sort(key=lambda x: x[1], reverse=True)
#             return [(img[0], img[2]) for img in relevant_images[:2]] # Return top 2 most relevant

#         except Exception as e:
#             logger.error(f"Error finding relevant images: {e}")
#             return []

#     def _llm_relevance_score(self, doc, question: str) -> float:
#         excerpt = doc.page_content[:500]
#         prompt = (
#             f"Rate the following document excerpt's relevance to the query on a scale from 0 to 1.\n"
#             f"Query: {question}\n"
#             f"Document excerpt: {excerpt}\n"
#             "Provide only the numeric score (e.g., 0.75)."
#         )
#         try:
#             score_str = self.llm.predict(prompt).strip()
#             return float(score_str)
#         except Exception as e:
#             logger.error(f"LLM relevance score error: {e}")
#             return 0.0

#     def deep_extract_info(self, doc, question: str) -> str:
#         prompt = f"""
#         Extract relevant information from the document that answers this query: {question}
        
#         Document text:
#         {doc.page_content}
        
#         Provide:
#         1. The direct answer from the text
#         2. Important context or related details
#         """
        
#         try:
#             extraction = self.llm.predict(prompt)
#             return extraction.strip()
#         except Exception as e:
#             logger.error(f"Deep extraction error: {e}")
#             return ""

#     def query(self, question: str, user_id: str, fast_mode: bool = False) -> Dict[str, any]:
#         try:
#             vectorstore = self.get_or_create_user_vectorstore(user_id)
#             k = 5 if fast_mode else 10
            
#             retriever = vectorstore.as_retriever(search_kwargs={"k": k})
            
#             try:
#                 compressor = LLMChainExtractor(llm=self.llm)
#                 retriever = ContextualCompressionRetriever(
#                     base_compressor=compressor,
#                     base_retriever=retriever
#                 )
#             except Exception as e:
#                 logger.info(f"Compression retriever not used: {e}")

#             docs = retriever.get_relevant_documents(question)
            
#             scored_docs = [(doc, self._llm_relevance_score(doc, question)) for doc in docs]
#             scored_docs.sort(key=lambda x: x[1], reverse=True)
#             ranked_docs = [doc for doc, _ in scored_docs]

#             if fast_mode:
#                 context = "\n\n".join(doc.page_content for doc in ranked_docs)
#                 sources = [f"Source: {doc.metadata.get('source', 'Unknown')} (Category: {doc.metadata.get('category', 'Unknown')})"
#                         for doc in ranked_docs]
                
#                 # Get markdown-formatted image links
#                 markdown_images = self.find_relevant_images(context, question)
                
#                 return {
#                     "context": context,
#                     "sources": sources,
#                     "markdown_images": markdown_images  # Return markdown formatted images
#                 }
#             else:
#                 extracted_details = []
#                 extraction_sources = []
#                 with concurrent.futures.ThreadPoolExecutor() as executor:
#                     futures = {executor.submit(self.deep_extract_info, doc, question): doc for doc in ranked_docs}
#                     for future in concurrent.futures.as_completed(futures):
#                         doc = futures[future]
#                         extracted_text = future.result()
#                         if extracted_text:
#                             extracted_details.append(extracted_text)
#                             extraction_sources.append(
#                                 f"Source: {doc.metadata.get('source', 'Unknown')} (Category: {doc.metadata.get('category', 'Unknown')})"
#                             )
                
#                 deep_context = "\n\n".join(extracted_details)
#             markdown_images = self.find_relevant_images(deep_context, question)
            
#             return {
#                 "context": deep_context,
#                 "sources": extraction_sources,
#                 "markdown_images": markdown_images  # Return markdown formatted images
#             }

#         except Exception as e:
#             logger.error(f"Error in RAG query: {e}")
#             return {"context": "", "sources": [], "markdown_images": []}
# # -----------------------------------------------------------------------------
# # Caching the Query: Fast responses for repeated queries.
# # -----------------------------------------------------------------------------
# @lru_cache(maxsize=100)
# def cached_query(question: str, user_id: str) -> str:
#     local_rag_agent = RAGAgent(base_pdf_folder="./user_docs", base_vector_db_path="./vector_store")
#     # Set fast_mode=False for high accuracy; set True for quicker (less detailed) responses.
#     result = local_rag_agent.query(question, user_id, fast_mode=False)
#     context = result.get("context", "")
#     sources = result.get("sources", [])
#     image_urls = result.get("image_urls", [])
#     image_markdown = "\n".join([f"![Related Image]({url})" for url in image_urls]) if image_urls else ""
#     return f"Context:\n{context}\n\nSources:\n" + "\n".join(sources) + "\n\nImage URLs:\n" + image_markdown

# # -----------------------------------------------------------------------------
# # Agent Creation: Builds the conversational agent using tools and memory.
# # -----------------------------------------------------------------------------
# def create_tools(user_id: str):
#     return [
#         Tool(
#             name="Query Validation",
#             func=query_validation_tool.run,
#             description="Use this tool to validate user queries."
#         ),
#         Tool(
#             name="Cybersecurity Check",
#             func=cybersecurity_tool.run,
#             description="Use this tool to perform security checks on user queries."
#         ),
#         Tool(
#             name="RAG Query Tool",
#             func=lambda q: cached_query(q, user_id),
#             description="Retrieves the most accurate, detailed context, sources, and image URLs from the document database."
#         ),
#     ]

# def create_agent_executor(chatbot_role: str, custom_rules: str, chatbot_tone: str,
#                           fallback_message: str, webapp_info: str,
#                           user_id: str, conversation_behavior: str):
#     tools = create_tools(user_id)
#     memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
#     system_prompt = (
#         "You are a chatbot with the role of {chatbot_role} and a {chatbot_tone} tone. "
#         "Your responses must be based ONLY on the context provided from the document database. "
#         "Provide precise, evidence-based answers including only the most accurate and relevant details. "
#         "Pass the image link in markdown"
#         "Do not use any external or generic knowledge. "
#         "If you cannot find a specific answer, respond with: '{fallback_message}'.\n\n"
#         "Follow these strict rules: {custom_rules}\n\n"
#         "Before answering, ALWAYS use the 'RAG Query Tool' to get the most accurate context from the document database. "
#         "Ensure your answer strictly adheres to that content.\n\n"
#         "Web App Info: {webapp_info}\n\n"
#         "Conversation Behavior: {conversation_behavior}\n\n"
#         "Chat History:\n{chat_history}\n\n"
#         "Human: {input}\n"
#         "AI:"
#     )
#     character_prompt = PromptTemplate(
#         input_variables=["chatbot_role", "chatbot_tone", "custom_rules", "fallback_message", "webapp_info",
#                          "conversation_behavior", "chat_history", "input"],
#         template=system_prompt
#     )
#     agent = initialize_agent(
#         tools,
#         ChatOpenAI(model_name='gpt-4o-mini', temperature=0),
#         agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
#         verbose=True,
#         memory=memory,
#         agent_kwargs={
#             "system_message": character_prompt.format(
#                 chatbot_role=chatbot_role,
#                 chatbot_tone=chatbot_tone,
#                 custom_rules=custom_rules,
#                 fallback_message=fallback_message,
#                 webapp_info=webapp_info,
#                 conversation_behavior=conversation_behavior,
#                 chat_history="{chat_history}",
#                 input="{input}"
#             )
#         }
#     )
#     return agent

# def format_chat_history(chat_history: List[Dict[str, str]]) -> str:
#     return "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in chat_history]).strip()

# def extract_relevant_info(full_response: str) -> str:
#     return full_response

# # -----------------------------------------------------------------------------
# # Main Query Processor: Integrates security checks, conversation memory, and agent execution.
# # -----------------------------------------------------------------------------
# def process_query(query: str, chat_history: List[Dict[str, str]] = [],
#                   chatbot_role: str = "Support Assistant", custom_rules: str = "",
#                   chatbot_tone: str = "friendly", fallback_message: str = "I cannot answer based solely on the provided data.",
#                   webapp_info: str = "Internal Document Database", user_id: str = "default_user",
#                   welcome_message: str = "Hello! How can I help you today?",
#                   conversation_behavior: str = "Maintain a concise and focused conversation.") -> str:
#     try:
#         if query.lower().strip() in ["", "hi", "hello", "hey", "hai"]:
#             chat_history.append({"role": "human", "content": query, "timestamp": str(datetime.now())})
#             chat_history.append({"role": "ai", "content": welcome_message, "timestamp": str(datetime.now())})
#             return welcome_message
#         if query_validation_tool.run(query) == "INVALID":
#             return "Your query contains potentially malicious content. Please rephrase your question."
#         if cybersecurity_tool.run(query) == "UNSAFE":
#             return "Your query contains potentially unsafe content. Please rephrase your question."
#         agent = create_agent_executor(
#             chatbot_role=chatbot_role,
#             custom_rules=custom_rules,
#             chatbot_tone=chatbot_tone,
#             fallback_message=fallback_message,
#             webapp_info=webapp_info,
#             conversation_behavior=conversation_behavior,
#             user_id=user_id
#         )
#         for message in chat_history:
#             if message["role"] == "human":
#                 agent.memory.chat_memory.add_user_message(message["content"])
#             else:
#                 agent.memory.chat_memory.add_ai_message(message["content"])
#         result = agent({"input": query})
#         full_response = result.get("output", fallback_message)
#         relevant_info = extract_relevant_info(full_response)
#         logger.info(f"Agent response: {full_response}")
#         chat_history.append({"role": "human", "content": query, "timestamp": str(datetime.now())})
#         chat_history.append({"role": "ai", "content": relevant_info, "timestamp": str(datetime.now())})
#         return relevant_info
#     except Exception as e:
#         logger.error(f"Error in process_query: {str(e)}")
#         error_msg = f"An error occurred: {str(e)}"
#         chat_history.append({"role": "human", "content": query, "timestamp": str(datetime.now())})
#         chat_history.append({"role": "ai", "content": error_msg, "timestamp": str(datetime.now())})
#         return error_msg

# # -----------------------------------------------------------------------------
# # Optional: Chat Summary Generator (for long conversations)
# # -----------------------------------------------------------------------------
# def generate_chat_summary(chat_history: List[Dict[str, str]]) -> str:
#     llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.7)
#     chat_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
#     prompt = f"Summarize the following conversation:\n{chat_text}\nSummary:"
#     summary = llm.predict(prompt)
#     logger.info(f"Generated chat summary: {summary.strip()}")
#     return summary.strip()

# # -----------------------------------------------------------------------------
# # Global Instance for Importing (e.g., in Django)
# # -----------------------------------------------------------------------------
# rag_agent = RAGAgent(base_pdf_folder="./user_docs", base_vector_db_path="./vector_store")














######################################################BEST

# import os
# import re
# import json
# import logging
# import shutil
# import time
# import hashlib
# from datetime import datetime
# from functools import lru_cache
# from typing import List, Dict

# from dotenv import load_dotenv
# import PyPDF2

# # LangChain & OpenAI Imports
# from langchain.embeddings import OpenAIEmbeddings
# from langchain.vectorstores import Chroma
# from langchain_openai import ChatOpenAI
# from langchain.agents import AgentExecutor, Tool, AgentType, initialize_agent
# from langchain.prompts import PromptTemplate
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain.retrievers import ContextualCompressionRetriever
# from langchain.retrievers.document_compressors import LLMChainExtractor
# from langchain.chains.conversation.memory import ConversationBufferMemory
# from langchain.tools import BaseTool  # Use BaseTool for custom tools

# # Configure Logging
# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)

# load_dotenv()

# # -----------------------------------------------------------------------------
# # Global API Key Initialization
# # -----------------------------------------------------------------------------
# GLOBAL_API_KEY = os.getenv("OPENAI_API_KEY")

# # -----------------------------------------------------------------------------
# # RAG Agent: Handles PDF ingestion, vector DB creation, and context retrieval
# # -----------------------------------------------------------------------------
# class RAGAgent:
#     def __init__(self, base_pdf_folder: str, base_vector_db_path: str, user=None):
#         """
#         Initialize the RAG Agent with paths and API key.
#         """
#         self.base_pdf_folder = base_pdf_folder
#         self.base_vector_db_path = base_vector_db_path
#         self.user = user

#         api_key = user.openai_api_key if user and hasattr(user, "openai_api_key") else GLOBAL_API_KEY
#         if not api_key:
#             raise ValueError("No API key available")

#         self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=api_key)
#         self.llm = ChatOpenAI(api_key=api_key, model="gpt-4o-mini", temperature=0)

#     def get_or_create_user_vectorstore(self, user_id: str):
#         user_vector_db_path = os.path.join(self.base_vector_db_path, f"user_{user_id}")
#         vectorstore = Chroma(persist_directory=user_vector_db_path, embedding_function=self.embeddings)
#         return vectorstore

#     def process_pdf_documents(self, pdf_folder: str, vectorstore):
#         """
#         Processes all PDFs in the given folder and adds their text (with metadata) to the vector store.
#         """
#         for filename in os.listdir(pdf_folder):
#             if filename.lower().endswith(".pdf"):
#                 file_path = os.path.join(pdf_folder, filename)
#                 try:
#                     documents = self.load_pdf_documents(file_path)
#                     if not documents:
#                         continue
#                     category = self.categorize_document(documents, filename)
#                     text_splitter = RecursiveCharacterTextSplitter(
#                         chunk_size=1000,
#                         chunk_overlap=200,
#                         separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
#                     )
#                     texts = text_splitter.split_text("\n\n".join(documents))
#                     metadatas = [{"source": filename, "category": category} for _ in texts]
#                     vectorstore.add_texts(texts, metadatas=metadatas)
#                     logger.info(f"Processed and vectorized {filename}")
#                 except Exception as e:
#                     logger.error(f"Error processing {filename}: {str(e)}")
#         vectorstore.persist()
#         logger.info(f"All PDFs processed in folder: {pdf_folder}")

#     def load_pdf_documents(self, filepath: str) -> List[str]:
#         """
#         Loads all pages from a PDF as a list of strings.
#         """
#         documents = []
#         try:
#             with open(filepath, 'rb') as file:
#                 pdf_reader = PyPDF2.PdfReader(file)
#                 for page in pdf_reader.pages:
#                     text = page.extract_text()
#                     if text:
#                         documents.append(text)
#             return documents
#         except Exception as e:
#             logger.error(f"Error loading PDF {filepath}: {str(e)}")
#             return []

#     def categorize_document(self, documents: List[str], filename: str) -> str:
#         """
#         Uses a simple LLM prompt to determine the main category of the document.
#         """
#         content = "\n".join(documents[:3])
#         prompt = f"""
#         Given the following content from a document, determine the main category it belongs to.
#         If multiple categories are present, choose the most dominant one.

#         Document filename: {filename}
#         Content preview:
#         {content[:1000]}...

#         Category:
#         """
#         response = self.llm.predict(prompt)
#         return response.strip()

#     def query(self, question: str, user_id: str) -> Dict[str, any]:
#         """
#         Retrieves relevant context from the vector store using a hybrid search approach.
#         The process uses:
#           1. Vector search (semantic similarity) with an optional compression retriever.
#           2. A refined re-ranking step that normalizes keyword frequency to pinpoint the most accurate information.
#         """
#         try:
#             vectorstore = self.get_or_create_user_vectorstore(user_id)
#             retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

#             # Optionally use a compression retriever for targeted context extraction.
#             try:
#                 compressor = LLMChainExtractor(llm=self.llm)
#                 retriever = ContextualCompressionRetriever(
#                     base_compressor=compressor,
#                     base_retriever=retriever
#                 )
#                 logger.info("Using ContextualCompressionRetriever for context extraction.")
#             except Exception as e:
#                 logger.info(f"Compression retriever not used due to error: {e}")

#             docs = retriever.get_relevant_documents(question)

#             # --- Enhanced Hybrid Re-Ranking ---
#             # Combine keyword frequency (normalized) as a measure of pinpoint accuracy.
#             def relevance_score(doc):
#                 # Compute raw frequency of each query word in the document.
#                 keyword_score = sum(doc.page_content.lower().count(word.lower()) for word in question.split())
#                 # Normalize score by the document's word count to avoid bias toward longer texts.
#                 normalized_score = keyword_score / (len(doc.page_content.split()) + 1)
#                 return normalized_score

#             # Sort documents using the normalized keyword relevance score.
#             docs = sorted(docs, key=lambda doc: relevance_score(doc), reverse=True)
#             # --------------------------------------------------

#             context = "\n\n".join([doc.page_content for doc in docs])
#             sources = [
#                 f"Source: {doc.metadata.get('source', 'Unknown')} (Category: {doc.metadata.get('category', 'Unknown')})"
#                 for doc in docs
#             ]

#             # Extract image URLs from the context (if any)
#             image_urls = re.findall(r'(https?://\S+\.(?:png|jpe?g|gif))', context, re.IGNORECASE)

#             return {"context": context, "sources": sources, "image_urls": list(set(image_urls))}
#         except Exception as e:
#             logger.error(f"Error in RAG query: {e}")
#             return {"context": "", "sources": [], "image_urls": []}

# # -----------------------------------------------------------------------------
# # Tools: Query Validation and Cybersecurity Check (subclassing BaseTool)
# # -----------------------------------------------------------------------------
# class QueryValidationTool(BaseTool):
#     name = "query_validation_tool"
#     description = "Checks if the user query is appropriate and free from potentially harmful content."

#     def _run(self, query: str) -> str:
#         if not query.strip() or len(query) > 1000:
#             return "INVALID"
#         inappropriate_patterns = [
#             r'http[s]?://',
#             r'www\.',
#             r'<[^>]*>',
#             r'script',
#             r'eval\(',
#             r'exec\(',
#             r'\[\[.*?\]\]',
#             r'\{\{.*?\}\}',
#         ]
#         for pattern in inappropriate_patterns:
#             if re.search(pattern, query, re.IGNORECASE):
#                 return "INVALID"
#         return "VALID"

#     async def _arun(self, query: str):
#         raise NotImplementedError("Async mode not supported.")

# class CybersecurityTool(BaseTool):
#     name = "cybersecurity_tool"
#     description = "Checks if the query contains any potentially malicious code or content."

#     def _run(self, query: str) -> str:
#         suspicious_patterns = [
#             r'SELECT.*FROM',
#             r'INSERT.*INTO',
#             r'UPDATE.*SET',
#             r'DELETE.*FROM',
#             r'DROP.*TABLE',
#             r'UNION.*SELECT',
#             r'rm -rf',
#             r'sudo',
#             r'chmod',
#             r'wget',
#             r'curl'
#         ]
#         for pattern in suspicious_patterns:
#             if re.search(pattern, query, re.IGNORECASE):
#                 return "UNSAFE"
#         suspicious_chars = ['&&', '||', ';', '|', '>', '<']
#         if any(char in query for char in suspicious_chars):
#             return "UNSAFE"
#         return "SAFE"

#     async def _arun(self, query: str):
#         raise NotImplementedError("Async mode not supported.")

# # Create tool instances
# query_validation_tool = QueryValidationTool()
# cybersecurity_tool = CybersecurityTool()

# # -----------------------------------------------------------------------------
# # Caching the Query: Ensures fast responses for repeated queries.
# # -----------------------------------------------------------------------------
# @lru_cache(maxsize=100)
# def cached_query(question: str, user_id: str) -> str:
#     local_rag_agent = RAGAgent(base_pdf_folder="./user_docs", base_vector_db_path="./vector_store")
#     result = local_rag_agent.query(question, user_id)
#     context = result.get("context", "")
#     sources = result.get("sources", [])
#     image_urls = result.get("image_urls", [])
#     image_markdown = ""
#     if image_urls:
#         image_markdown = f"![Related Image]({image_urls[0]})"
#     return f"Context:\n{context}\n\nSources:\n" + "\n".join(sources) + "\n\nImage URL:\n" + image_markdown

# # -----------------------------------------------------------------------------
# # Agent Creation: Builds the conversational agent using the provided tools and memory.
# # -----------------------------------------------------------------------------
# def create_tools(user_id: str):
#     return [
#         Tool(
#             name="Query Validation",
#             func=query_validation_tool.run,
#             description="Use this tool to validate user queries."
#         ),
#         Tool(
#             name="Cybersecurity Check",
#             func=cybersecurity_tool.run,
#             description="Use this tool to perform security checks on user queries."
#         ),
#         Tool(
#             name="RAG Query Tool",
#             func=lambda q: cached_query(q, user_id),
#             description="Retrieves highly specific context, sources, and image URLs strictly from the document database."
#         ),
#     ]

# def create_agent_executor(chatbot_role: str, custom_rules: str, chatbot_tone: str,
#                           fallback_message: str, webapp_info: str,
#                           user_id: str, conversation_behavior: str):
#     tools = create_tools(user_id)
#     # Using a ConversationBufferMemory to maintain chat history
#     memory = ConversationBufferMemory(
#         memory_key="chat_history",
#         return_messages=True
#     )

#     # Updated system prompt with explicit instructions for pinpoint, evidence-based answers.
#     system_prompt = (
#         "You are a chatbot with the role of {chatbot_role} and a {chatbot_tone} tone. "
#         "Your responses must be based ONLY on the context provided from the document database. "
#         "Provide a precise and pinpoint answer using direct quotes and specific evidence when available. "
#         "Do not incorporate any external or generic knowledge. "
#         "If you cannot find a specific answer within the provided context, respond with: '{fallback_message}'.\n\n"
#         "Follow these strict rules: {custom_rules}\n\n"
#         "Always include the image link if its avilable"
#         "Before answering, ALWAYS use the 'RAG Query Tool' to retrieve the most up-to-date and accurate context from the document database. "
#         "Ensure that your final answer strictly adheres to the retrieved content.\n\n"
#         "Web App Info: {webapp_info}\n\n"
#         "Conversation Behavior: {conversation_behavior}\n\n"
#         "Chat History:\n{chat_history}\n\n"
#         "Human: {input}\n"
#         "AI:"
#     )

#     character_prompt = PromptTemplate(
#         input_variables=["chatbot_role", "chatbot_tone", "custom_rules", "fallback_message", "webapp_info",
#                          "conversation_behavior", "chat_history", "input"],
#         template=system_prompt
#     )

#     agent = initialize_agent(
#         tools,
#         ChatOpenAI(model_name='gpt-4o-mini', temperature=0),
#         agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
#         verbose=True,
#         memory=memory,
#         agent_kwargs={
#             "system_message": character_prompt.format(
#                 chatbot_role=chatbot_role,
#                 chatbot_tone=chatbot_tone,
#                 custom_rules=custom_rules,
#                 fallback_message=fallback_message,
#                 webapp_info=webapp_info,
#                 conversation_behavior=conversation_behavior,
#                 chat_history="{chat_history}",
#                 input="{input}"
#             )
#         }
#     )
#     return agent

# def format_chat_history(chat_history: List[Dict[str, str]]) -> str:
#     """
#     Formats conversation history for inclusion in the prompt.
#     """
#     formatted_history = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in chat_history])
#     return formatted_history.strip()

# def extract_relevant_info(full_response: str) -> str:
#     """
#     For now, we return the full response. Further extraction or summarization can be done here.
#     """
#     return full_response

# # -----------------------------------------------------------------------------
# # Main Query Processor: Integrates security checks, conversation memory, and agent execution.
# # -----------------------------------------------------------------------------
# def process_query(query: str, chat_history: List[Dict[str, str]] = [],
#                   chatbot_role: str = "Support Assistant", custom_rules: str = "",
#                   chatbot_tone: str = "friendly", fallback_message: str = "I cannot answer based solely on the provided data.",
#                   webapp_info: str = "Internal Document Database", user_id: str = "default_user",
#                   welcome_message: str = "Hello! How can I help you today?",
#                   conversation_behavior: str = "Maintain a concise and focused conversation.") -> str:
#     try:
#         # Basic greeting handling
#         if query.lower().strip() in ["", "hi", "hello", "hey", "hai"]:
#             chat_history.append({
#                 "role": "human",
#                 "content": query,
#                 "timestamp": str(datetime.now())
#             })
#             chat_history.append({
#                 "role": "ai",
#                 "content": welcome_message,
#                 "timestamp": str(datetime.now())
#             })
#             return welcome_message

#         # Validate and secure the query
#         if query_validation_tool.run(query) == "INVALID":
#             return "Your query contains potentially malicious content. Please rephrase your question."
#         if cybersecurity_tool.run(query) == "UNSAFE":
#             return "Your query contains potentially unsafe content. Please rephrase your question."

#         # Create the conversational agent with memory
#         agent = create_agent_executor(
#             chatbot_role=chatbot_role,
#             custom_rules=custom_rules,
#             chatbot_tone=chatbot_tone,
#             fallback_message=fallback_message,
#             webapp_info=webapp_info,
#             conversation_behavior=conversation_behavior,
#             user_id=user_id
#         )

#         # Load chat history into agent's memory
#         for message in chat_history:
#             if message["role"] == "human":
#                 agent.memory.chat_memory.add_user_message(message["content"])
#             else:
#                 agent.memory.chat_memory.add_ai_message(message["content"])

#         # Get the agent's response
#         result = agent({"input": query})
#         full_response = result.get("output", fallback_message)
#         relevant_info = extract_relevant_info(full_response)

#         logger.info(f"Agent response: {full_response}")

#         # Update chat history
#         chat_history.append({
#             "role": "human",
#             "content": query,
#             "timestamp": str(datetime.now())
#         })
#         chat_history.append({
#             "role": "ai",
#             "content": relevant_info,
#             "timestamp": str(datetime.now())
#         })

#         return relevant_info

#     except Exception as e:
#         logger.error(f"Error in process_query: {str(e)}")
#         error_msg = f"An error occurred: {str(e)}"
#         chat_history.append({
#             "role": "human",
#             "content": query,
#             "timestamp": str(datetime.now())
#         })
#         chat_history.append({
#             "role": "ai",
#             "content": error_msg,
#             "timestamp": str(datetime.now())
#         })
#         return error_msg

# # -----------------------------------------------------------------------------
# # Optional: Chat Summary Generator (for long conversations)
# # -----------------------------------------------------------------------------
# def generate_chat_summary(chat_history: List[Dict[str, str]]) -> str:
#     llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.7)
#     chat_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
#     prompt = f"Summarize the following conversation:\n{chat_text}\nSummary:"
#     summary = llm.predict(prompt)
#     logger.info(f"Generated chat summary: {summary.strip()}")
#     return summary.strip()

# # -----------------------------------------------------------------------------
# # Global Instance for Importing (fixes the import error in Django)
# # -----------------------------------------------------------------------------
# rag_agent = RAGAgent(base_pdf_folder="./user_docs", base_vector_db_path="./vector_store")
























###### BETTEREREEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE


import os
import re
import json
import logging
import hashlib
from datetime import datetime
from functools import lru_cache
from typing import List, Dict

import PyPDF2
from dotenv import load_dotenv

from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain.tools import BaseTool, Tool
from langchain.agents import AgentType, initialize_agent

# ------------------------ Setup Logging and Environment ------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Global persistent conversation memory per user (in-memory store)
conversation_memories: Dict[str, ConversationBufferMemory] = {}

# Initialize a base LLM using your API key
api_key = os.getenv("OPENAI_API_KEY")
base_llm = ChatOpenAI(api_key=api_key, model="gpt-4o-mini", temperature=0)

# ------------------------ Advanced RAG Agent Class ------------------------
class RAGAgent:
    def __init__(self, base_pdf_folder: str, base_vector_db_path: str, user=None):
        self.base_pdf_folder = base_pdf_folder
        self.base_vector_db_path = base_vector_db_path
        self.user = user

        key = user.openai_api_key if user and hasattr(user, "openai_api_key") else os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("No API key available")

        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=key)
        self.llm = ChatOpenAI(api_key=key, model="gpt-4o-mini", temperature=0)

    def get_or_create_user_vectorstore(self, user_id: str):
        user_vector_db_path = os.path.join(self.base_vector_db_path, f"user_{user_id}")
        vectorstore = Chroma(persist_directory=user_vector_db_path, embedding_function=self.embeddings)
        return vectorstore

    def process_pdf_documents(self, pdf_folder: str, vectorstore):
        for filename in os.listdir(pdf_folder):
            if filename.lower().endswith(".pdf"):
                file_path = os.path.join(pdf_folder, filename)
                try:
                    pages = self.load_pdf_documents(file_path)
                    category = self.categorize_document(pages, filename)

                    texts = []
                    metadatas = []
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=500,
                        chunk_overlap=200,
                        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
                    )

                    for i, page_text in enumerate(pages):
                        chunks = text_splitter.split_text(page_text)
                        for j, chunk in enumerate(chunks):
                            texts.append(chunk)
                            metadatas.append({
                                "source": filename,
                                "category": category,
                                "page_number": str(i + 1),
                                "chunk_id": f"{filename}_p{i+1}_c{j+1}",
                                "content": chunk[:100]  # Store first 100 chars as preview
                            })

                    vectorstore.add_texts(texts, metadatas=metadatas)
                    logger.info(f"Processed and vectorized {filename} with {len(texts)} chunks")
                except Exception as e:
                    logger.error(f"Error processing {filename}: {str(e)}")
        vectorstore.persist()

    def load_pdf_documents(self, filepath: str) -> List[str]:
        pages = []
        try:
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
            return pages
        except Exception as e:
            logger.error(f"Error loading PDF {filepath}: {str(e)}")
            return []

    def categorize_document(self, pages: List[str], filename: str) -> str:
        content = "\n".join(pages[:3])
        prompt = f"""
Given the following content from a document, determine its main category and subcategories.
Document filename: {filename}
Content preview:
{content[:1500]}...

Provide the category in the format: MAIN_CATEGORY/SUBCATEGORY"""
        response = self.llm.predict(prompt)
        return response.strip()

    def generate_search_queries(self, original_question: str) -> List[str]:
        prompt = f"""
Given the following question related to complex documents: "{original_question}"
Generate 3 different search queries that capture key aspects needed for precise retrieval:
1. A direct rephrasing of the original question.
2. A query focusing on key concepts and terminologies.
3. A query exploring implicit or related aspects.
Format each query on a new line."""
        response = self.llm.predict(prompt)
        queries = [q.strip() for q in response.split("\n") if q.strip()]
        queries.append(original_question)
        return list(set(queries))

    def query(self, question: str, user_id: str, conversation_behavior: str = "") -> Dict[str, str]:
        try:
            vectorstore = self.get_or_create_user_vectorstore(user_id)

            retriever = vectorstore.as_retriever(
                search_type="mmr",
                search_kwargs={
                    "k": 15,
                    "fetch_k": 30,
                    "lambda_mult": 0.7
                }
            )

            # Generate multiple search queries
            search_queries = self.generate_search_queries(question)
            all_docs = []

            # Retrieve documents for each query
            for query in search_queries:
                try:
                    docs = retriever.get_relevant_documents(query)
                    all_docs.extend(docs)
                except Exception as e:
                    logger.error(f"Error retrieving documents for query '{query}': {str(e)}")
                    continue

            if not all_docs:
                return {
                    "answer": "I couldn't find any relevant information in the documents to answer your question.",
                    "sources": []
                }

            # Deduplicate documents while preserving order
            seen = set()
            unique_docs = []
            for doc in all_docs:
                doc_hash = hash(doc.page_content)
                if doc_hash not in seen:
                    seen.add(doc_hash)
                    unique_docs.append(doc)

            # --- Re-ranking Step ---
            # Compute a simple relevance score for each document based on term frequency from the original question.
            def relevance_score(doc):
                score = 0
                for word in question.split():
                    score += doc.page_content.lower().count(word.lower())
                return score

            unique_docs.sort(key=lambda doc: relevance_score(doc), reverse=True)
            # -------------------------

            # Combine context with metadata
            contexts = []
            for doc in unique_docs:
                try:
                    context = f"[Source: {doc.metadata.get('source', 'Unknown')}, Page: {doc.metadata.get('page_number', 'N/A')}]\n{doc.page_content}"
                    contexts.append(context)
                except Exception as e:
                    logger.error(f"Error processing document metadata: {str(e)}")
                    continue

            combined_context = "\n\n".join(contexts)

            if not combined_context.strip():
                return {
                    "answer": "I found some documents but couldn't process them properly. Please try again.",
                    "sources": []
                }

            # Generate answer with stronger grounding and enhanced prompt instructions
            prompt_template = """
You are a precise information retrieval expert. Your task is to answer the question using ONLY the provided context.
Follow these rules strictly:
1. Only use information explicitly stated in the context.
2. If the answer isn't fully contained in the context, say "I don't have enough information to fully answer this question."
3. First, list the evidence with its source and page reference, then provide a well-structured answer.
4. Be precise and specific in your answer.
5. always make sure to add the corresponding image url as markdown with the answer Fetch the correct image URL.

Context:
{context}

Question:
{question}

Provide a well-structured answer with citations:"""

            PROMPT = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
            prompt_text = PROMPT.format(context=combined_context, question=question)

            answer = self.llm.predict(prompt_text)

            # Prepare response with sources
            response = {
                "answer": answer.strip(),
                "sources": []
            }

            # Add source metadata
            for doc in unique_docs:
                try:
                    source_info = {
                        "filename": doc.metadata.get('source', 'Unknown'),
                        "category": doc.metadata.get('category', 'Unknown'),
                        "page": doc.metadata.get('page_number', 'N/A')
                    }
                    if source_info not in response["sources"]:
                        response["sources"].append(source_info)
                except Exception as e:
                    logger.error(f"Error processing source metadata: {str(e)}")
                    continue

            return response

        except Exception as e:
            logger.error(f"Error in RAG query: {str(e)}")
            return {
                "answer": "I encountered an error while processing your question. Please try again.",
                "sources": []
            }


# Instantiate the RAG agent
rag_agent = RAGAgent(base_pdf_folder="./user_docs", base_vector_db_path="./vector_store")

# ------------------------ Tool Definitions ------------------------
class QueryValidationTool(BaseTool):
    name = "query_validation_tool"
    description = "Checks if the user query is appropriate and not offensive."

    def _run(self, query: str) -> str:
        if not query.strip() or len(query) > 1000:
            return "INVALID"
        inappropriate_patterns = [
            r'http[s]?://', r'www\.', r'<[^>]*>', r'script', r'eval\(',
            r'exec\(', r'\[\[.*?\]\]', r'\{\{.*?\}\}',
        ]
        for pattern in inappropriate_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return "INVALID"
        return "VALID"

    async def _arun(self, query: str):
        raise NotImplementedError("This tool does not support async")

class CybersecurityTool(BaseTool):
    name = "cybersecurity_tool"
    description = "Checks if the query contains any potentially malicious content or code."

    def _run(self, query: str) -> str:
        suspicious_patterns = [
            r'SELECT.*FROM', r'INSERT.*INTO', r'UPDATE.*SET', r'DELETE.*FROM',
            r'DROP.*TABLE', r'UNION.*SELECT', r'rm -rf', r'sudo', r'chmod', r'wget', r'curl'
        ]
        for pattern in suspicious_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return "UNSAFE"
        if any(char in query for char in ['&&', '||', ';', '|', '>', '<']):
            return "UNSAFE"
        return "SAFE"

    async def _arun(self, query: str):
        raise NotImplementedError("This tool does not support async")

query_validation_tool = QueryValidationTool()
cybersecurity_tool = CybersecurityTool()

@lru_cache(maxsize=100)
def cached_query(question: str, user_id: str, conversation_behavior: str) -> str:
    response = rag_agent.query(question, user_id, conversation_behavior=conversation_behavior)
    return response["answer"]

def process_rag_response(response) -> str:
    if isinstance(response, dict) and "answer" in response:
        return response["answer"]
    return response

def create_tools(user_id: str, conversation_behavior: str):
    return [
        Tool(
            name="Query Validation",
            func=query_validation_tool.run,
            description="Use this to validate user queries"
        ),
        Tool(
            name="Cybersecurity Check",
            func=cybersecurity_tool.run,
            description="Use this to perform security checks on user queries"
        ),
        Tool(
            name="RAG Query Tool",
            func=lambda q: process_rag_response(cached_query(q, user_id, conversation_behavior)),
            description="Retrieve and extract only the necessary information from the document database"
        ),
    ]

def create_agent_executor(chatbot_role: str, custom_rules: str, chatbot_tone: str, fallback_message: str,
                          webapp_info: str, user_id: str, conversation_behavior: str, memory: ConversationBufferMemory):
    tools = create_tools(user_id, conversation_behavior)
    character_prompt = PromptTemplate(
        input_variables=["chatbot_role", "chatbot_tone", "tools", "fallback_message", "webapp_info", "input", "chat_history", "conversation_behavior"],
        template=(
            "You are a chatbot with the role of {chatbot_role} and maintain a {chatbot_tone} tone.\n"
            "ONLY use the retrieved response from the RAG Query Tool exactly as provided.\n"
            "Do not add or modify the information. If no relevant information is found, respond with: {fallback_message}.\n\n"
            "You have access to the following tools: {tools}\n\n"
            "Always make sure to add the corresponding image url as markdown with the answer fetch the correct image URL"
            "Chat History:\n{chat_history}\n\n"
            "Human: {input}\n"
            "AI:"
        )
    )
    agent = initialize_agent(
        tools,
        ChatOpenAI(model_name='gpt-4o-mini', temperature=0),
        agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
        verbose=True,
        memory=memory,
        agent_kwargs={
            "system_message": character_prompt.format(
                chatbot_role=chatbot_role,
                custom_rules=custom_rules,
                chatbot_tone=chatbot_tone,
                tools=tools,
                fallback_message=fallback_message,
                webapp_info=webapp_info,
                conversation_behavior=conversation_behavior,
                chat_history="{chat_history}",
                input="{input}"
            ),
        }
    )
    return agent

# ------------------------ Query Processing ------------------------
def process_query(query: str, chat_history: List[Dict[str, str]] = None, chatbot_role: str = "",
                  custom_rules: str = "", chatbot_tone: str = "", fallback_message: str = "",
                  webapp_info: str = "", user_id: str = "", welcome_message: str = "",
                  conversation_behavior: str = "") -> str:
    try:
        if chat_history is None:
            chat_history = []

        # Retrieve or initialize persistent conversation memory for the user
        if user_id in conversation_memories:
            memory = conversation_memories[user_id]
        else:
            memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
            conversation_memories[user_id] = memory

        # Handle basic greetings
        if query.lower().strip() in ["", "hi", "hello", "hey", "hai"]:
            chat_history.append({
                "role": "human",
                "content": query,
                "timestamp": str(datetime.now())
            })
            chat_history.append({
                "role": "ai",
                "content": welcome_message,
                "timestamp": str(datetime.now())
            })
            return welcome_message

        # Validate query
        if query_validation_tool.run(query) == "INVALID":
            return "Your query contains potentially malicious content. Please rephrase your question."
        if cybersecurity_tool.run(query) == "UNSAFE":
            return "Your query contains potentially malicious content. Please rephrase your question."

        # Create agent executor using persistent memory
        agent = create_agent_executor(
            chatbot_role=chatbot_role,
            custom_rules=custom_rules,
            chatbot_tone=chatbot_tone,
            fallback_message=fallback_message,
            webapp_info=webapp_info,
            conversation_behavior=conversation_behavior,
            user_id=user_id,
            memory=memory
        )

        # Update persistent memory with chat history
        for message in chat_history:
            if message["role"] == "human":
                memory.chat_memory.add_user_message(message["content"])
            else:
                memory.chat_memory.add_ai_message(message["content"])

        # Get agent response
        result = agent({"input": query})
        logger.info(f"Agent Result: {result}")

        response_to_use = result.get("output", "").strip() or fallback_message

        # Update conversation memory and chat_history with current turn
        chat_history.append({
            "role": "human",
            "content": query,
            "timestamp": str(datetime.now())
        })
        chat_history.append({
            "role": "ai",
            "content": response_to_use,
            "timestamp": str(datetime.now())
        })
        memory.chat_memory.add_user_message(query)
        memory.chat_memory.add_ai_message(response_to_use)

        return response_to_use

    except Exception as e:
        logger.error(f"Error in process_query: {str(e)}")
        error_msg = f"An error occurred: {str(e)}"
        chat_history.append({
            "role": "human",
            "content": query,
            "timestamp": str(datetime.now())
        })
        chat_history.append({
            "role": "ai",
            "content": error_msg,
            "timestamp": str(datetime.now())
        })
        return error_msg


def generate_chat_summary(chat_history: List[Dict[str, str]]) -> str:
    llm_summary = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.7)
    chat_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
    prompt = f"Summarize the following chat conversation:\n{chat_text}\nSummary:"
    logger.info(f"Generating summary for chat history: {chat_text}")
    summary = llm_summary.predict(prompt)
    logger.info(f"Generated summary: {summary.strip()}")
    return summary.strip()


























##Goooddddddddddddddddddddddddddddddddd


# import os
# import re
# import json
# import logging
# import hashlib
# from datetime import datetime
# from functools import lru_cache
# from typing import List, Dict

# import PyPDF2
# from dotenv import load_dotenv

# from langchain.embeddings import OpenAIEmbeddings
# from langchain.vectorstores import Chroma
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain_openai import ChatOpenAI
# from langchain.prompts import PromptTemplate
# from langchain.chains.conversation.memory import ConversationBufferMemory
# from langchain.tools import BaseTool, Tool
# from langchain.agents import AgentType, initialize_agent

# # ------------------------ Setup Logging and Environment ------------------------
# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)
# load_dotenv()

# # Global persistent conversation memory per user (in-memory store)
# conversation_memories: Dict[str, ConversationBufferMemory] = {}

# # Initialize a base LLM using your API key
# api_key = os.getenv("OPENAI_API_KEY")
# base_llm = ChatOpenAI(api_key=api_key, model="gpt-4o-mini", temperature=0)

# # ------------------------ Advanced RAG Agent Class ------------------------
# class RAGAgent:
#     def __init__(self, base_pdf_folder: str, base_vector_db_path: str, user=None):
#         self.base_pdf_folder = base_pdf_folder
#         self.base_vector_db_path = base_vector_db_path
#         self.user = user

#         key = user.openai_api_key if user and hasattr(user, "openai_api_key") else os.getenv("OPENAI_API_KEY")
#         if not key:
#             raise ValueError("No API key available")

#         self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=key)
#         self.llm = ChatOpenAI(api_key=key, model="gpt-4o-mini", temperature=0)

#     def get_or_create_user_vectorstore(self, user_id: str):
#         user_vector_db_path = os.path.join(self.base_vector_db_path, f"user_{user_id}")
#         vectorstore = Chroma(persist_directory=user_vector_db_path, embedding_function=self.embeddings)
#         return vectorstore

#     def process_pdf_documents(self, pdf_folder: str, vectorstore):
#         for filename in os.listdir(pdf_folder):
#             if filename.lower().endswith(".pdf"):
#                 file_path = os.path.join(pdf_folder, filename)
#                 try:
#                     pages = self.load_pdf_documents(file_path)
#                     category = self.categorize_document(pages, filename)

#                     texts = []
#                     metadatas = []
#                     text_splitter = RecursiveCharacterTextSplitter(
#                         chunk_size=500,
#                         chunk_overlap=200,
#                         separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
#                     )

#                     for i, page_text in enumerate(pages):
#                         chunks = text_splitter.split_text(page_text)
#                         for j, chunk in enumerate(chunks):
#                             texts.append(chunk)
#                             metadatas.append({
#                                 "source": filename,
#                                 "category": category,
#                                 "page_number": str(i + 1),
#                                 "chunk_id": f"{filename}_p{i+1}_c{j+1}",
#                                 "content": chunk[:100]  # Store first 100 chars as preview
#                             })

#                     vectorstore.add_texts(texts, metadatas=metadatas)
#                     logger.info(f"Processed and vectorized {filename} with {len(texts)} chunks")
#                 except Exception as e:
#                     logger.error(f"Error processing {filename}: {str(e)}")
#         vectorstore.persist()

#     def load_pdf_documents(self, filepath: str) -> List[str]:
#         pages = []
#         try:
#             with open(filepath, 'rb') as file:
#                 pdf_reader = PyPDF2.PdfReader(file)
#                 for page in pdf_reader.pages:
#                     text = page.extract_text()
#                     if text:
#                         pages.append(text)
#             return pages
#         except Exception as e:
#             logger.error(f"Error loading PDF {filepath}: {str(e)}")
#             return []

#     def categorize_document(self, pages: List[str], filename: str) -> str:
#         content = "\n".join(pages[:3])
#         prompt = f"""
# Given the following content from a document, determine its main category and subcategories.
# Document filename: {filename}
# Content preview:
# {content[:1500]}...

# Provide the category in the format: MAIN_CATEGORY/SUBCATEGORY"""
#         response = self.llm.predict(prompt)
#         return response.strip()

#     def generate_search_queries(self, original_question: str) -> List[str]:
#         prompt = f"""
# Given this question: "{original_question}"
# Generate 3 different search queries that could help find relevant information:
# 1. A direct rephrasing of the original question
# 2. A query focusing on key concepts and terminology
# 3. A query exploring related or implicit aspects

# Format each query on a new line."""

#         response = self.llm.predict(prompt)
#         queries = [q.strip() for q in response.split("\n") if q.strip()]
#         queries.append(original_question)
#         return list(set(queries))

#     def query(self, question: str, user_id: str, conversation_behavior: str = "") -> Dict[str, str]:
#         try:
#             vectorstore = self.get_or_create_user_vectorstore(user_id)

#             retriever = vectorstore.as_retriever(
#                 search_type="mmr",
#                 search_kwargs={
#                     "k": 15,
#                     "fetch_k": 30,
#                     "lambda_mult": 0.7
#                 }
#             )

#             # Generate multiple search queries
#             search_queries = self.generate_search_queries(question)
#             all_docs = []

#             # Retrieve documents for each query
#             for query in search_queries:
#                 try:
#                     docs = retriever.get_relevant_documents(query)
#                     all_docs.extend(docs)
#                 except Exception as e:
#                     logger.error(f"Error retrieving documents for query '{query}': {str(e)}")
#                     continue

#             if not all_docs:
#                 return {
#                     "answer": "I couldn't find any relevant information in the documents to answer your question.",
#                     "sources": []
#                 }

#             # Deduplicate documents while preserving order
#             seen = set()
#             unique_docs = []
#             for doc in all_docs:
#                 doc_hash = hash(doc.page_content)
#                 if doc_hash not in seen:
#                     seen.add(doc_hash)
#                     unique_docs.append(doc)

#             # Combine context with metadata
#             contexts = []
#             for doc in unique_docs:
#                 try:
#                     context = f"[Source: {doc.metadata.get('source', 'Unknown')}, Page: {doc.metadata.get('page_number', 'N/A')}]\n{doc.page_content}"
#                     contexts.append(context)
#                 except Exception as e:
#                     logger.error(f"Error processing document metadata: {str(e)}")
#                     continue

#             combined_context = "\n\n".join(contexts)

#             if not combined_context.strip():
#                 return {
#                     "answer": "I found some documents but couldn't process them properly. Please try again.",
#                     "sources": []
#                 }

#             # Generate answer with stronger grounding
#             prompt_template = """
# You are a precise information retrieval expert. Your task is to answer the question using ONLY the provided context.
# Follow these rules strictly:
# 1. Only use information explicitly stated in the context
# 2. If the answer isn't fully contained in the context, say "I don't have enough information to fully answer this question"
# 3. Cite the source and page number when providing information
# 4. Be precise and specific in your answer

# Context:
# {context}

# Question:
# {question}

# Provide a well-structured answer with citations:"""

#             PROMPT = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
#             prompt_text = PROMPT.format(context=combined_context, question=question)

#             answer = self.llm.predict(prompt_text)

#             # Prepare response with sources
#             response = {
#                 "answer": answer.strip(),
#                 "sources": []
#             }

#             # Add source metadata
#             for doc in unique_docs:
#                 try:
#                     source_info = {
#                         "filename": doc.metadata.get('source', 'Unknown'),
#                         "category": doc.metadata.get('category', 'Unknown'),
#                         "page": doc.metadata.get('page_number', 'N/A')
#                     }
#                     if source_info not in response["sources"]:
#                         response["sources"].append(source_info)
#                 except Exception as e:
#                     logger.error(f"Error processing source metadata: {str(e)}")
#                     continue

#             return response

#         except Exception as e:
#             logger.error(f"Error in RAG query: {str(e)}")
#             return {
#                 "answer": "I encountered an error while processing your question. Please try again.",
#                 "sources": []
#             }

# # Instantiate the RAG agent
# rag_agent = RAGAgent(base_pdf_folder="./user_docs", base_vector_db_path="./vector_store")

# # ------------------------ Tool Definitions ------------------------
# class QueryValidationTool(BaseTool):
#     name = "query_validation_tool"
#     description = "Checks if the user query is appropriate and not offensive."

#     def _run(self, query: str) -> str:
#         if not query.strip() or len(query) > 1000:
#             return "INVALID"
#         inappropriate_patterns = [
#             r'http[s]?://', r'www\.', r'<[^>]*>', r'script', r'eval\(',
#             r'exec\(', r'\[\[.*?\]\]', r'\{\{.*?\}\}',
#         ]
#         for pattern in inappropriate_patterns:
#             if re.search(pattern, query, re.IGNORECASE):
#                 return "INVALID"
#         return "VALID"

#     async def _arun(self, query: str):
#         raise NotImplementedError("This tool does not support async")

# class CybersecurityTool(BaseTool):
#     name = "cybersecurity_tool"
#     description = "Checks if the query contains any potentially malicious content or code."

#     def _run(self, query: str) -> str:
#         suspicious_patterns = [
#             r'SELECT.*FROM', r'INSERT.*INTO', r'UPDATE.*SET', r'DELETE.*FROM',
#             r'DROP.*TABLE', r'UNION.*SELECT', r'rm -rf', r'sudo', r'chmod', r'wget', r'curl'
#         ]
#         for pattern in suspicious_patterns:
#             if re.search(pattern, query, re.IGNORECASE):
#                 return "UNSAFE"
#         if any(char in query for char in ['&&', '||', ';', '|', '>', '<']):
#             return "UNSAFE"
#         return "SAFE"

#     async def _arun(self, query: str):
#         raise NotImplementedError("This tool does not support async")

# query_validation_tool = QueryValidationTool()
# cybersecurity_tool = CybersecurityTool()

# @lru_cache(maxsize=100)
# def cached_query(question: str, user_id: str, conversation_behavior: str) -> str:
#     response = rag_agent.query(question, user_id, conversation_behavior=conversation_behavior)
#     return response["answer"]

# def process_rag_response(response) -> str:
#     if isinstance(response, dict) and "answer" in response:
#         return response["answer"]
#     return response

# def create_tools(user_id: str, conversation_behavior: str):
#     return [
#         Tool(
#             name="Query Validation",
#             func=query_validation_tool.run,
#             description="Use this to validate user queries"
#         ),
#         Tool(
#             name="Cybersecurity Check",
#             func=cybersecurity_tool.run,
#             description="Use this to perform security checks on user queries"
#         ),
#         Tool(
#             name="RAG Query Tool",
#             func=lambda q: process_rag_response(cached_query(q, user_id, conversation_behavior)),
#             description="Retrieve and extract only the necessary information from the document database"
#         ),
#     ]

# def create_agent_executor(chatbot_role: str, custom_rules: str, chatbot_tone: str, fallback_message: str,
#                           webapp_info: str, user_id: str, conversation_behavior: str, memory: ConversationBufferMemory):
#     tools = create_tools(user_id, conversation_behavior)
#     character_prompt = PromptTemplate(
#         input_variables=["chatbot_role", "chatbot_tone", "tools", "fallback_message", "webapp_info", "input", "chat_history", "conversation_behavior"],
#         template=(
#             "You are a chatbot with the role of {chatbot_role} and maintain a {chatbot_tone} tone.\n"
#             "ONLY use the retrieved response from the RAG Query Tool exactly as provided.\n"
#             "Do not add or modify the information. If no relevant information is found, respond with: {fallback_message}.\n\n"
#             "You have access to the following tools: {tools}\n\n"
#             "Chat History:\n{chat_history}\n\n"
#             "Human: {input}\n"
#             "AI:"
#         )
#     )
#     agent = initialize_agent(
#         tools,
#         ChatOpenAI(model_name='gpt-4o-mini', temperature=0),
#         agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
#         verbose=True,
#         memory=memory,
#         agent_kwargs={
#             "system_message": character_prompt.format(
#                 chatbot_role=chatbot_role,
#                 custom_rules=custom_rules,
#                 chatbot_tone=chatbot_tone,
#                 tools=tools,
#                 fallback_message=fallback_message,
#                 webapp_info=webapp_info,
#                 conversation_behavior=conversation_behavior,
#                 chat_history="{chat_history}",
#                 input="{input}"
#             ),
#         }
#     )
#     return agent

# # ------------------------ Query Processing ------------------------
# def process_query(query: str, chat_history: List[Dict[str, str]] = None, chatbot_role: str = "",
#                   custom_rules: str = "", chatbot_tone: str = "", fallback_message: str = "",
#                   webapp_info: str = "", user_id: str = "", welcome_message: str = "",
#                   conversation_behavior: str = "") -> str:
#     try:
#         if chat_history is None:
#             chat_history = []

#         # Retrieve or initialize persistent conversation memory for the user
#         if user_id in conversation_memories:
#             memory = conversation_memories[user_id]
#         else:
#             memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
#             conversation_memories[user_id] = memory

#         # Handle basic greetings
#         if query.lower().strip() in ["", "hi", "hello", "hey", "hai"]:
#             chat_history.append({
#                 "role": "human",
#                 "content": query,
#                 "timestamp": str(datetime.now())
#             })
#             chat_history.append({
#                 "role": "ai",
#                 "content": welcome_message,
#                 "timestamp": str(datetime.now())
#             })
#             return welcome_message

#         # Validate query
#         if query_validation_tool.run(query) == "INVALID":
#             return "Your query contains potentially malicious content. Please rephrase your question."
#         if cybersecurity_tool.run(query) == "UNSAFE":
#             return "Your query contains potentially malicious content. Please rephrase your question."

#         # Create agent executor using persistent memory
#         agent = create_agent_executor(
#             chatbot_role=chatbot_role,
#             custom_rules=custom_rules,
#             chatbot_tone=chatbot_tone,
#             fallback_message=fallback_message,
#             webapp_info=webapp_info,
#             conversation_behavior=conversation_behavior,
#             user_id=user_id,
#             memory=memory
#         )

#         # Update persistent memory with chat history
#         for message in chat_history:
#             if message["role"] == "human":
#                 memory.chat_memory.add_user_message(message["content"])
#             else:
#                 memory.chat_memory.add_ai_message(message["content"])

#         # Get agent response
#         result = agent({"input": query})
#         logger.info(f"Agent Result: {result}")

#         response_to_use = result.get("output", "").strip() or fallback_message

#         # Update conversation memory and chat_history with current turn
#         chat_history.append({
#             "role": "human",
#             "content": query,
#             "timestamp": str(datetime.now())
#         })
#         chat_history.append({
#             "role": "ai",
#             "content": response_to_use,
#             "timestamp": str(datetime.now())
#         })
#         memory.chat_memory.add_user_message(query)
#         memory.chat_memory.add_ai_message(response_to_use)

#         return response_to_use

#     except Exception as e:
#         logger.error(f"Error in process_query: {str(e)}")
#         error_msg = f"An error occurred: {str(e)}"
#         chat_history.append({
#             "role": "human",
#             "content": query,
#             "timestamp": str(datetime.now())
#         })
#         chat_history.append({
#             "role": "ai",
#             "content": error_msg,
#             "timestamp": str(datetime.now())
#         })
#         return error_msg


# def generate_chat_summary(chat_history: List[Dict[str, str]]) -> str:
#     llm_summary = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.7)
#     chat_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
#     prompt = f"Summarize the following chat conversation:\n{chat_text}\nSummary:"
#     logger.info(f"Generating summary for chat history: {chat_text}")
#     summary = llm_summary.predict(prompt)
#     logger.info(f"Generated summary: {summary.strip()}")
#     return summary.strip()




