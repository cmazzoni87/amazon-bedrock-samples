"""Evaluation monitor component for the Streamlit dashboard."""

import streamlit as st
import pandas as pd
import time
import os
import json
import logging
from pathlib import Path
from ..utils.benchmark_runner import run_benchmark_async, sync_evaluations_from_files, dashboard_logger

class EvaluationMonitorComponent:
    """Component for monitoring active evaluations."""
    
    def render(self):
        """Render the evaluation monitor component."""
        dashboard_logger.info("Rendering evaluation monitor component")
        
        # Sync evaluation statuses from files
        sync_evaluations_from_files()
        
        # Add a UI indicator for the log file location
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
        st.info(f"📋 Logs available at: {log_dir}")
        
        st.subheader("Active Evaluations")
        
        # Get current session time
        current_session_start = st.session_state.get('session_start_time', time.time())
        if 'session_start_time' not in st.session_state:
            st.session_state.session_start_time = current_session_start
            dashboard_logger.info(f"Set session start time to {current_session_start}")
        
        # Check if there are any active evaluations
        dashboard_logger.debug("Retrieving active evaluations")
        active_evals = self._get_active_evaluations(current_session_start)
        dashboard_logger.info(f"Found {len(active_evals)} active evaluations")
        
        if not active_evals:
            st.info("No active evaluations in this session. Go to Setup tab to create and run evaluations.")
        else:
            # Display active evaluations with status indicators
            for i, eval_config in enumerate(active_evals):
                with st.container():
                    col1, col2, col3 = st.columns([3, 2, 1])
                    
                    with col1:
                        st.write(f"**{eval_config['name']}**")
                        
                        # Display status as colored indicator
                        status = eval_config.get('status', 'unknown')
                        if status == "in-progress":
                            st.markdown("🔄 **Status**: <span style='color:blue'>In Progress</span>", unsafe_allow_html=True)
                        elif status == "failed":
                            st.markdown("❌ **Status**: <span style='color:red'>Failed</span>", unsafe_allow_html=True)
                        elif status == "completed":
                            st.markdown("✅ **Status**: <span style='color:green'>Completed</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"⚠️ **Status**: {status.capitalize()}")
                    
                    with col2:
                        # Display details
                        st.write(f"Task: {eval_config['task_type']}")
                        st.write(f"Models: {len(eval_config['selected_models'])}")
                        
                        # Display elapsed time if available
                        if 'start_time' in eval_config:
                            end_time = eval_config.get('end_time', time.time())
                            elapsed = end_time - eval_config['start_time']
                            st.write(f"Elapsed: {self._format_time(elapsed)}")
                    
                    with col3:
                        # Add view logs button
                        if 'logs_dir' in eval_config and os.path.exists(eval_config['logs_dir']):
                            if st.button("View Logs", key=f"logs_{i}"):
                                self._show_logs(eval_config)
                                dashboard_logger.info(f"Showing logs for evaluation {eval_config['id']}")
                        
                        # Debug button to view full evaluation details
                        if st.button("Debug Info", key=f"debug_{i}"):
                            dashboard_logger.info(f"Showing debug info for evaluation {eval_config['id']}")
                            with st.expander("Evaluation Details"):
                                st.json({k: str(v) if k == 'csv_data' else v for k, v in eval_config.items()})
                        
                        # Allow cancellation (not implemented in this version)
                        st.button(
                            "Cancel",
                            key=f"cancel_{i}",
                            help="Cancel this evaluation (not implemented in this version)"
                        )
                
                # Show error if present
                if 'error' in eval_config and eval_config['error']:
                    with st.expander("Show Error"):
                        st.error(eval_config['error'])
                        dashboard_logger.error(f"Evaluation {eval_config['id']} error: {eval_config['error']}")
                
                st.divider()
            
            # Add refresh button for active evaluations
            if st.button("Refresh Status", on_click=sync_evaluations_from_files):
                dashboard_logger.info("Manually refreshed evaluation statuses")
        
        st.subheader("Available Evaluations")
        
        # Get all evaluations that are not active and not completed
        available_evals = [
            e for e in st.session_state.evaluations 
            if e["id"] not in [a["id"] for a in active_evals]
            and e["status"] not in ["in-progress", "running", "completed"]
        ]
        
        if not available_evals:
            st.info("No available evaluations. Go to Setup tab to create new evaluations.")
        else:
            # Create a table of available evaluations
            eval_data = []
            for eval_config in available_evals:
                eval_data.append({
                    "ID": eval_config["id"],
                    "Name": eval_config["name"],
                    "Task Type": eval_config["task_type"],
                    "Models": len(eval_config["selected_models"]),
                    "Status": eval_config["status"].capitalize(),
                    "Created": pd.to_datetime(eval_config["created_at"]).strftime("%Y-%m-%d %H:%M")
                })
            
            eval_df = pd.DataFrame(eval_data)
            st.dataframe(eval_df)
            
            # Allow running selected evaluations
            st.subheader("Run Selected Evaluations")
            
            # Multiselect for evaluation IDs
            selected_eval_ids = st.multiselect(
                "Select evaluations to run",
                options=[e["id"] for e in available_evals],
                format_func=lambda x: next((e["name"] for e in available_evals if e["id"] == x), x)
            )
            
            if selected_eval_ids:
                st.button(
                    "Run Selected Evaluations",
                    on_click=self._run_selected_evaluations,
                    args=(selected_eval_ids,)
                )
    
    def _get_active_evaluations(self, session_start_time):
        """Get evaluations that are active in the current session."""
        active_evals = []
        
        # First get from session state
        if hasattr(st.session_state, 'evaluations'):
            for eval_config in st.session_state.evaluations:
                # Check if this evaluation was started in this session
                status_file = Path(eval_config.get("output_dir", "benchmark_results")) / f"eval_{eval_config['id']}_status.json"
                if status_file.exists():
                    try:
                        with open(status_file, 'r') as f:
                            status_data = json.load(f)
                            # Include if started in this session or still in-progress
                            if (status_data.get('start_time', 0) >= session_start_time or 
                                status_data.get('status') == 'in-progress'):
                                
                                # Merge status data with eval config
                                eval_data = eval_config.copy()
                                eval_data.update(status_data)
                                active_evals.append(eval_data)
                    except:
                        pass
                        
                # Also include any that are marked as running in session state
                elif eval_config.get('status') in ['running', 'in-progress']:
                    active_evals.append(eval_config)
                    
        return active_evals
    
    def _format_time(self, seconds):
        """Format seconds into a readable time string."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
    
    def _show_logs(self, eval_config):
        """Show logs for an evaluation."""
        logs_dir = eval_config.get('logs_dir')
        if not logs_dir or not os.path.exists(logs_dir):
            st.error("Logs directory not found.")
            return
            
        # Show stdout log
        stdout_log = Path(logs_dir) / "stdout.log"
        if stdout_log.exists():
            with st.expander("Standard Output Log", expanded=True):
                with open(stdout_log, 'r') as f:
                    log_content = f.read()
                st.code(log_content)
                
        # Show stderr log
        stderr_log = Path(logs_dir) / "stderr.log"
        if stderr_log.exists():
            with st.expander("Error Log"):
                with open(stderr_log, 'r') as f:
                    log_content = f.read()
                if log_content.strip():
                    st.code(log_content)
                else:
                    st.info("No errors reported.")
    
    def _run_selected_evaluations(self, eval_ids):
        """Run the selected evaluations."""
        dashboard_logger.info(f"Running selected evaluations: {eval_ids}")
        for eval_id in eval_ids:
            for eval_config in st.session_state.evaluations:
                if eval_config["id"] == eval_id:
                    try:
                        run_benchmark_async(eval_config)
                        st.success(f"Evaluation '{eval_config['name']}' started.")
                        dashboard_logger.info(f"Successfully started evaluation: {eval_config['name']} (ID: {eval_id})")
                        
                        # Show log file location to user
                        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
                        st.info(f"Check logs in: {log_dir}")
                    except Exception as e:
                        error_msg = f"Error starting evaluation: {str(e)}"
                        dashboard_logger.exception(error_msg)
                        st.error(error_msg)
                    break