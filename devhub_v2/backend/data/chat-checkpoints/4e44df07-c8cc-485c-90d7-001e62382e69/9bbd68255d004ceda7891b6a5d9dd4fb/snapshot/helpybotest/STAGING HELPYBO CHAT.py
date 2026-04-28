                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          chatbot_logic.py                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      from datetime import datetime
import os
import re
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, Tool, ZeroShotAgent
from langchain.tools import BaseTool
from langchain.chains import LLMChain, RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.agents import AgentAction, AgentFinish
from typing import List, Dict
import PyPDF2
import json
import logging
import shutil
from functools import lru_cache
from langchain import hub
from langchain.prompts.prompt import PromptTemplate
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain.agents import create_react_agent
from langchain.agents import AgentExecutor
from langchain.agents import AgentType, initialize_agent
from langchain_core.prompts import PromptTemplate
from langchain.chains.question_answering import load_qa_chain
import hashlib
import time
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor

logger = logging.getLogger(__name__)

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

llm = ChatOpenAI(api_key=api_key, model="gpt-4o-mini", temperature=0)

class RAGAgent:
    def __init__(self, base_pdf_folder: str, base_vector_db_path: str, user=None):
        """
        Initialize the RAG Agent with base paths and user-specific API key
        """
        self.base_pdf_folder = base_pdf_folder
        self.base_vector_db_path = base_vector_db_path
        self.user = user

        api_key = user.openai_api_key if user else os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("No API key available")

        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=api_key)
        self.llm = ChatOpenAI(api_key=api_key, model="gpt-4o-mini", temperature=0)

    def get_or_create_user_vectorstore(self, user_id: str):
        user_vector_db_path = os.path.join(self.base_vector_db_path, f"user_{user_id}")
        vectorstore = Chroma(persist_directory=user_vector_db_path, embedding_function=self.embeddings)
        return vectorstore


    def process_pdf_documents(self, pdf_folder, vectorstore):
        for filename in os.listdir(pdf_folder):
            if filename.endswith(".pdf"):
                file_path = os.path.join(pdf_folder, filename)
                try:
                    documents = self.load_pdf_documents(file_path)
                    category = self.categorize_document(documents, filename)
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=2000,
                        chunk_overlap=400,
                        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
                    )
                    texts = text_splitter.split_text("\n\n".join(documents))
                    metadatas = [{"source": filename, "category": category} for _ in texts]
                    vectorstore.add_texts(texts, metadatas=metadatas)
                    logger.info(f"Processed and vectorized {filename}")
                except Exception as e:
                    logger.error(f"Error processing {filename}: {str(e)}")
        logger.info(f"Processed and vectorized all PDF documents in {pdf_folder}")

        vectorstore.persist()

    def load_pdf_documents(self, filepath):
        documents = []
        try:
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    documents.append(page.extract_text())
            return documents
        except Exception as e:
            logger.error(f"Error loading PDF {filepath}: {str(e)}")
            return []

    def categorize_document(self, documents, filename):
        content = "\n".join(documents[:3])
        prompt = f"""
        Given the following content from a document, determine the main category it belongs to.
        If multiple categories are present, choose the most dominant one.

        Document filename: {filename}
        Content preview:
        {content[:1000]}...

        Category:
        """
        response = self.llm.predict(prompt)
        return response.strip()

    def query(self, question: str, user_id: str) -> str:
        try:
            vectorstore = self.get_or_create_user_vectorstore(user_id)
            retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
            docs = retriever.get_relevant_documents(question)
            context = "\n\n".join([doc.page_content for doc in docs])
            sources = [f"Source: {doc.metadata.get('source', 'Unknown')} (Category: {doc.metadata.get('category', 'Unknown')})" for doc in docs]
            return context, sources

        except Exception as e:
            logger.error(f"Error in RAG query: {e}")
            return "", []

rag_agent = RAGAgent(base_pdf_folder="./user_docs", base_vector_db_path="./vector_store")


class QueryValidationTool(BaseTool):
    name = "query_validation_tool"
    description = "Checks if the user query is appropriate and not offensive."

    def _run(self, query: str) -> str:
        # Check for empty or too long queries
        if not query.strip() or len(query) > 1000:
            return "INVALID"

        # Define patterns inline
        inappropriate_patterns = [
            r'http[s]?://',
            r'www\.',
            r'<[^>]*>',
            r'script',
            r'eval\(',
            r'exec\(',
            r'\[\[.*?\]\]',
            r'\{\{.*?\}\}',
        ]

        # Check against inappropriate patterns
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
        # Define patterns inline
        suspicious_patterns = [
            r'SELECT.*FROM',
            r'INSERT.*INTO',
            r'UPDATE.*SET',
            r'DELETE.*FROM',
            r'DROP.*TABLE',
            r'UNION.*SELECT',
            r'rm -rf',
            r'sudo',
            r'chmod',
            r'wget',
            r'curl'
        ]

        # Check patterns
        for pattern in suspicious_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return "UNSAFE"

        # Check suspicious characters
        suspicious_chars = ['&&', '||', ';', '|', '>', '<']
        if any(char in query for char in suspicious_chars):
            return "UNSAFE"

        return "SAFE"

    async def _arun(self, query: str):
        raise NotImplementedError("This tool does not support async")

query_validation_tool = QueryValidationTool()
cybersecurity_tool = CybersecurityTool()



@lru_cache(maxsize=100)
def cached_query(question: str, user_id: str) -> str:
    context, sources = rag_agent.query(question, user_id)
    return f"Context: {context}\n\nSources:\n" + "\n".join(sources)

def create_tools(user_id):
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
            func=lambda q: cached_query(q, user_id),
            description="Use this tool to retrieve relevant information from the document database"
        ),
    ]





def create_agent_executor(chatbot_role, custom_rules, chatbot_tone, fallback_message, webapp_info, user_id,conversation_behavior):
    tools = create_tools(user_id)

    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

    character_prompt = PromptTemplate(
        input_variables=["chatbot_role", "chatbot_tone", "tools", "fallback_message", "webapp_info", "input", "chat_history","conversation_behavior"],
        template="""You are a chatbot with the role of {chatbot_role}. Maintain a {chatbot_tone} tone.
        Only use ENGLISH language while answering the user's query.

        CRITICAL INSTRUCTION: You must ONLY use information from the RAG Query Tool responses.
        Never use your own knowledge or information that wasn't explicitly returned by the RAG Query Tool.
        If the RAG Query Tool doesn't return relevant information, respond with: {fallback_message}.

        Before providing ANY answer:
        1. You MUST first use the RAG Query Tool
        2. Only respond based on the tool's returned context
        3. If the context doesn't contain the answer, admit you cannot answer
        4. first look for the  answer in the {webapp_info} and then answer the user's query based on the context.
        5. make sure to feth and pass the  urls or any links if its avilablein the provided answer if its relevant or similar to what user asked give the most relevant output.

        This is a conversational style you should follow: {conversation_behavior}

        You have access to the following tools: {tools}

        {fallback_message}

        Chat History:
        {chat_history}

        Human: {input}
        AI: """
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

def format_chat_history(chat_history: List[Dict[str, str]]) -> str:
    formatted_history = ""
    for message in chat_history:
        role = message["role"]
        content = message["content"]
        formatted_history += f"{role.capitalize()}: {content}\n"
    return formatted_history.strip()

def extract_relevant_info(full_response: str) -> str:
    return full_response







def process_query(query: str, chat_history: List[Dict[str, str]] = [], chatbot_role: str = "", custom_rules: str = "", chatbot_tone: str = "", fallback_message: str = "", webapp_info: str = "", user_id: str = "", welcome_message: str = "", conversation_behavior: str = "") -> str:
    try:
        # Basic greetings check - return welcome message directly
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

        validation_result = query_validation_tool.run(query)
        if validation_result == "INVALID":
            return "Your query contains potentially malicious content. Please rephrase your question."

        security_result = cybersecurity_tool.run(query)
        if security_result == "UNSAFE":
            return "Your query contains potentially malicious content. Please rephrase your question."

        agent = create_agent_executor(
            chatbot_role=chatbot_role,
            custom_rules=custom_rules,
            chatbot_tone=chatbot_tone,
            fallback_message=fallback_message,
            webapp_info=webapp_info,
            conversation_behavior=conversation_behavior,
            user_id=user_id
        )

        # Add chat history to agent's memory
        for message in chat_history:
            if message["role"] == "human":
                agent.memory.chat_memory.add_user_message(message["content"])
            else:
                agent.memory.chat_memory.add_ai_message(message["content"])

        result = agent({"input": query})

        full_response = result.get("output", fallback_message)

        relevant_info = extract_relevant_info(full_response)

        logger.info(f"Full RAG agent response: {full_response}")
        logger.info(f"Extracted relevant information: {relevant_info}")

        # Update chat history with the new interaction
        chat_history.append({
            "role": "human",
            "content": query,
            "timestamp": str(datetime.now())
        })
        chat_history.append({
            "role": "ai",
            "content": relevant_info,
            "timestamp": str(datetime.now())
        })

        return relevant_info

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






import logging

logger = logging.getLogger(__name__)

def generate_chat_summary(chat_history):
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.7)
    chat_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
    prompt = f"Summarize the following chat conversation:\n{chat_text}\nSummary:"
    logger.info(f"Generating summary for chat history: {chat_text}")
    summary = llm.predict(prompt)
    logger.info(f"Generated summary: {summary.strip()}")
    return summary.strip()



