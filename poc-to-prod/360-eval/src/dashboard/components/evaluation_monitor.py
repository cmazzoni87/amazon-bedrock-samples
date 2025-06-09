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
        
        # Debug information about current session state
        print(f"Current evaluations in session state: {len(st.session_state.evaluations)}")
        for i, eval_config in enumerate(st.session_state.evaluations):
            print(f"Evaluation {i+1}: ID={eval_config['id']}, Name={eval_config['name']}, Status={eval_config['status']}")
        
        # Sync evaluation statuses from files
        sync_evaluations_from_files()
        
        # Set up auto-refresh
        if 'last_refresh_time' not in st.session_state:
            st.session_state.last_refresh_time = time.time()
            
        # Check if 10 seconds have passed since last refresh
        current_time = time.time()
        if current_time - st.session_state.last_refresh_time > 10:
            sync_evaluations_from_files()
            st.session_state.last_refresh_time = current_time
            dashboard_logger.info("Auto-refreshed evaluation statuses")
            
        # Add a UI indicator for the log file location
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
        st.info(f"📋 Logs available at: {log_dir}")
        
        # Get current session time
        current_session_start = st.session_state.get('session_start_time', time.time())
        if 'session_start_time' not in st.session_state:
            st.session_state.session_start_time = current_session_start
            dashboard_logger.info(f"Set session start time to {current_session_start}")
        
        # Retrieve all evaluations for this session
        dashboard_logger.debug("Retrieving session evaluations")
        session_evals = self._get_session_evaluations(current_session_start)
        
        # Separate active and recently completed evaluations
        active_evals = [e for e in session_evals if e.get('status') in ['in-progress', 'running']]
        completed_evals = [e for e in session_evals if e.get('status') == 'completed' and 
                          e.get('end_time', 0) > current_time - 60]  # Show completed in last minute
        failed_evals = [e for e in session_evals if e.get('status') == 'failed' and
                       e.get('end_time', 0) > current_time - 60]  # Show failed in last minute
        
        # Display active and recent evaluations
        st.subheader("Active & Recent Evaluations")
        all_display_evals = active_evals + completed_evals + failed_evals
        
        if not all_display_evals:
            st.info("No active evaluations in this session. Go to Setup tab to create and run evaluations.")
        else:
            dashboard_logger.info(f"Displaying {len(all_display_evals)} evaluations (Active: {len(active_evals)}, " +
                                  f"Recently Completed: {len(completed_evals)}, Failed: {len(failed_evals)})")
            
            # Display evaluations with status indicators
            for i, eval_config in enumerate(all_display_evals):
                with st.container():
                    col1, col2, col3 = st.columns([3, 2, 1])
                    
                    with col1:
                        st.write(f"**{eval_config['name']}**")
                        
                        # Display status as colored indicator
                        status = eval_config.get('status', 'unknown')
                        if status in ['in-progress', 'running']:
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
                        # Show report link for completed evaluations
                        if status == "completed" and 'results' in eval_config and eval_config['results']:
                            report_path = eval_config['results']
                            # Check if file exists
                            if os.path.exists(report_path):
                                # Create report link
                                report_filename = os.path.basename(report_path)
                                # Convert to file:// URL for local file
                                file_url = f"file://{os.path.abspath(report_path)}"
                                st.markdown(f"[📊 Open Report]({file_url})", unsafe_allow_html=True)
                                dashboard_logger.info(f"Provided link to report: {report_path}")
                            else:
                                st.error("Report file not found")
                        
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
                
                # Show error if present
                if 'error' in eval_config and eval_config['error']:
                    with st.expander("Show Error"):
                        st.error(eval_config['error'])
                        dashboard_logger.error(f"Evaluation {eval_config['id']} error: {eval_config['error']}")
                
                st.divider()
            
            # Add refresh button for active evaluations
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.button("Refresh Now", on_click=sync_evaluations_from_files):
                    dashboard_logger.info("Manually refreshed evaluation statuses")
            with col2:
                st.caption("Status auto-refreshes every 10 seconds")
        
        # Display Available Evaluations Section
        st.subheader("Available Evaluations")
        
        # Debug session state
        print(f"Checking for available evaluations in {len(st.session_state.evaluations)} total evaluations")
        
        # Get all evaluations regardless of status (we'll filter in the UI if needed)
        available_evals = list(st.session_state.evaluations)
        
        # Print available evaluations for debugging
        for i, e in enumerate(available_evals):
            print(f"Evaluation {i+1}: ID={e['id']}, Name={e['name']}, Status={e['status']}")
        
        if not available_evals:
            st.info("No available evaluations. Go to Setup tab to create new evaluations.")
        else:
            dashboard_logger.info(f"Found {len(available_evals)} available evaluations")
            # Create a table of available evaluations
            eval_data = []
            for eval_config in available_evals:
                eval_data.append({
                    "ID": eval_config["id"],
                    "Name": eval_config["name"],
                    "Task Type": eval_config["task_type"],
                    "Models": len(eval_config["selected_models"]),
                    "Status": eval_config["status"].capitalize(),
                    "Created": pd.to_datetime(eval_config["created_at"]).strftime("%Y-%m-%d %H:%M") if eval_config.get("created_at") else "N/A"
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
                if st.button("Run Selected Evaluations"):
                    self._run_selected_evaluations(selected_eval_ids)
    
    def _get_session_evaluations(self, session_start_time):
        """Get all evaluations for the current session, including completed ones."""
        session_evals = []
        
        # Get from session state
        if hasattr(st.session_state, 'evaluations'):
            for eval_config in st.session_state.evaluations:
                # Check if this evaluation was started in this session
                status_file = Path(eval_config.get("output_dir", "benchmark_results")) / f"eval_{eval_config['id']}_status.json"
                if status_file.exists():
                    try:
                        with open(status_file, 'r') as f:
                            status_data = json.load(f)
                            # Include if started in this session
                            if status_data.get('start_time', 0) >= session_start_time:
                                # Merge status data with eval config
                                eval_data = eval_config.copy()
                                eval_data.update(status_data)
                                session_evals.append(eval_data)
                    except:
                        pass
                        
        return session_evals
        
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
    
    def _show_report(self, report_path):
        """Display an HTML report."""
        # Check if report exists
        if not os.path.exists(report_path):
            st.error(f"Report file not found: {report_path}")
            return
        
        # Read HTML content
        with open(report_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Display HTML
        st.components.v1.html(html_content, height=600, scrolling=True)
    
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
        
        # Track successful starts for UI feedback
        started_evals = []
        failed_evals = []
        
        # Process each selected evaluation
        for eval_id in eval_ids:
            for eval_config in st.session_state.evaluations:
                if eval_config["id"] == eval_id:
                    try:
                        # Make sure the evaluation configuration is valid
                        if not eval_config.get("selected_models") or not eval_config.get("judge_models"):
                            raise ValueError("Missing required configuration: models or judge models")
                            
                        # Run the benchmark
                        run_benchmark_async(eval_config)
                        started_evals.append(eval_config["name"])
                        dashboard_logger.info(f"Successfully started evaluation: {eval_config['name']} (ID: {eval_id})")
                    except Exception as e:
                        error_msg = f"Error starting evaluation '{eval_config['name']}': {str(e)}"
                        dashboard_logger.exception(error_msg)
                        failed_evals.append((eval_config["name"], str(e)))
                    break
        
        # Show success/failure messages
        if started_evals:
            st.success(f"Started evaluations: {', '.join(started_evals)}")
            
            # Show log file location to user
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
            st.info(f"Check logs in: {log_dir}")
            
        if failed_evals:
            for name, error in failed_evals:
                st.error(f"Failed to start '{name}': {error}")
                
        # Force refresh of UI state
        if started_evals:
            sync_evaluations_from_files()