import nest_asyncio
import streamlit as st
from agents import get_sql_agent
from agno.agent import Agent
from agno.utils.log import logger
from utils import (
    CUSTOM_CSS,
    add_message,
    display_tool_calls,
    rename_session_widget,
    session_selector_widget,
    sidebar_widget,
)
from dotenv import load_dotenv

load_dotenv()
nest_asyncio.apply()
st.set_page_config(
    page_title="RetailIQ: Advanced Retail Analytics",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load custom CSS with dark mode support
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def main() -> None:
    ####################################################################
    # App header
    ####################################################################
    st.markdown(
        "<h1 class='main-title'>RetailIQ: Advanced Retail Analytics</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p class='subtitle'>RetailIQ is an intelligent SQL Agent for analyzing retail data, inventory trends, and sales metrics</p>",
        unsafe_allow_html=True,
    )

    ####################################################################
    # Debug Mode Toggle
    ####################################################################
    if "debug_mode_value" not in st.session_state:
        st.session_state["debug_mode_value"] = False

    DEBUG_MODE = st.sidebar.checkbox(
        "Debug Mode",
        value=st.session_state["debug_mode_value"],
        key="debug_mode_widget"
    )
    st.session_state["debug_mode_value"] = DEBUG_MODE

    ####################################################################
    # Model selector
    ####################################################################
    model_options = {
        "gpt-4o-mini": "openai:gpt-4o-mini",
        "gpt-4o": "openai:gpt-4o",
    }
    selected_model = st.sidebar.selectbox(
        "Select a model",
        options=list(model_options.keys()),
        index=0,
        key="model_selector",
    )
    model_id = model_options[selected_model]

    ####################################################################
    # Initialize Agent
    ####################################################################
    sql_agent: Agent
    if (
            "sql_agent" not in st.session_state
            or st.session_state["sql_agent"] is None
            or st.session_state.get("current_model") != model_id
            or st.session_state.get("debug_mode_value") != DEBUG_MODE
    ):
        logger.info("---*--- Creating new SQL agent ---*---")
        sql_agent = get_sql_agent(model_id=model_id, debug_mode=DEBUG_MODE)
        st.session_state["sql_agent"] = sql_agent
        st.session_state["current_model"] = model_id
    else:
        sql_agent = st.session_state["sql_agent"]

    ####################################################################
    # Load Agent Session from the database
    ####################################################################
    try:
        st.session_state["sql_agent_session_id"] = sql_agent.load_session()
    except Exception:
        st.warning("Could not create Agent session, is the database running?")
        return

    ####################################################################
    # Load runs from memory
    ####################################################################
    agent_runs = sql_agent.memory.runs
    if len(agent_runs) > 0:
        logger.debug("Loading run history")
        st.session_state["messages"] = []
        for _run in agent_runs:
            if _run.message is not None:
                add_message(_run.message.role, _run.message.content)
            if _run.response is not None:
                add_message("assistant", _run.response.content, _run.response.tools)
    else:
        logger.debug("No run history found")
        st.session_state["messages"] = []

    ####################################################################
    # Sidebar
    ####################################################################
    sidebar_widget()

    ####################################################################
    # Get user input
    ####################################################################
    if prompt := st.chat_input("👋 Ask me about sales, inventory, customers, or promotions!"):
        add_message("user", prompt)

    ####################################################################
    # Display chat history
    ####################################################################
    for message in st.session_state["messages"]:
        if message["role"] in ["user", "assistant"]:
            _content = message["content"]
            if _content is not None:
                with st.chat_message(message["role"]):
                    # Display tool calls if they exist in the message and debug mode is enabled
                    if DEBUG_MODE and "tool_calls" in message and message["tool_calls"]:
                        display_tool_calls(st.empty(), message["tool_calls"])
                    st.markdown(_content)

    ####################################################################
    # Generate response for user message
    ####################################################################
    last_message = (
        st.session_state["messages"][-1] if st.session_state["messages"] else None
    )
    if last_message and last_message.get("role") == "user":
        question = last_message["content"]
        with st.chat_message("assistant"):
            # Create container for tool calls if debug mode is enabled
            tool_calls_container = st.empty() if DEBUG_MODE else None
            resp_container = st.empty()
            with st.spinner("🤔 Thinking..."):
                response = ""
                try:
                    # Run the agent and stream the response
                    run_response = sql_agent.run(
                        question, stream=True, stream_intermediate_steps=True
                    )
                    for _resp_chunk in run_response:
                        # Display tool calls if available and debug mode is enabled
                        if DEBUG_MODE and _resp_chunk.tools and len(_resp_chunk.tools) > 0:
                            display_tool_calls(tool_calls_container, _resp_chunk.tools)

                        # Display response if available and event is RunResponse
                        if (
                                _resp_chunk.event == "RunResponse"
                                and _resp_chunk.content is not None
                        ):
                            response += _resp_chunk.content.replace("$", "&#36;")
                            resp_container.markdown(response)

                    add_message("assistant", response, sql_agent.run_response.tools)
                except Exception as e:
                    logger.exception(e)
                    error_message = f"Sorry, I encountered an error: {str(e)}"
                    add_message("assistant", error_message)
                    st.error(error_message)

    ####################################################################
    # Session selector
    ####################################################################
    session_selector_widget(sql_agent, model_id)
    rename_session_widget(sql_agent)


if __name__ == "__main__":
    main()