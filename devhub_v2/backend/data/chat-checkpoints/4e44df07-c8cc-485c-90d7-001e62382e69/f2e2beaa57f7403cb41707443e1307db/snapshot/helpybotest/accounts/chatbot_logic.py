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

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except ImportError:
    from langchain_openai import ChatOpenAI
    from langchain.embeddings import OpenAIEmbeddings

try:
    from langchain_community.vectorstores import Chroma
except ImportError:
    from langchain.vectorstores import Chroma

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

try:
    from langchain_classic.prompts import PromptTemplate
except ImportError:
    from langchain.prompts import PromptTemplate

try:
    from langchain_classic.chains.conversation.memory import ConversationBufferMemory
except ImportError:
    from langchain.chains.conversation.memory import ConversationBufferMemory

try:
    from langchain_classic.tools import BaseTool, Tool
except ImportError:
    from langchain.tools import BaseTool, Tool

try:
    from langchain_classic.agents import AgentType, initialize_agent
except ImportError:
    from langchain.agents import AgentType, initialize_agent


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
load_dotenv()

conversation_memories: Dict[str, ConversationBufferMemory] = {}


api_key = os.getenv("OPENAI_API_KEY")
base_llm = ChatOpenAI(api_key=api_key, model="gpt-4o-mini", temperature=0)


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


            search_queries = self.generate_search_queries(question)
            all_docs = []


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

            seen = set()
            unique_docs = []
            for doc in all_docs:
                doc_hash = hash(doc.page_content)
                if doc_hash not in seen:
                    seen.add(doc_hash)
                    unique_docs.append(doc)


            def relevance_score(doc):
                score = 0
                for word in question.split():
                    score += doc.page_content.lower().count(word.lower())
                return score

            unique_docs.sort(key=lambda doc: relevance_score(doc), reverse=True)

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

            response = {
                "answer": answer.strip(),
                "sources": []
            }

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

rag_agent = RAGAgent(base_pdf_folder="./user_docs", base_vector_db_path="./vector_store")


class QueryValidationTool(BaseTool):
    name: str = "query_validation_tool"
    description: str = "Checks if the user query is appropriate and not offensive."

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
    name: str = "cybersecurity_tool"
    description: str = "Checks if the query contains any potentially malicious content or code."

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

def process_query(query: str, chat_history: List[Dict[str, str]] = None, chatbot_role: str = "",
                  custom_rules: str = "", chatbot_tone: str = "", fallback_message: str = "",
                  webapp_info: str = "", user_id: str = "", welcome_message: str = "",
                  conversation_behavior: str = "") -> str:
    try:
        if chat_history is None:
            chat_history = []

        if user_id in conversation_memories:
            memory = conversation_memories[user_id]
        else:
            memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
            conversation_memories[user_id] = memory


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

        if query_validation_tool.run(query) == "INVALID":
            return "Your query contains potentially malicious content. Please rephrase your question."
        if cybersecurity_tool.run(query) == "UNSAFE":
            return "Your query contains potentially malicious content. Please rephrase your question."

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
