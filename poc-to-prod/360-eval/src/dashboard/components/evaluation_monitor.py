"""Evaluation monitor component for the Streamlit dashboard."""

import streamlit as st
import pandas as pd
import time
import os
import json
import logging
import base64
from datetime import datetime
from pathlib import Path
from ..utils.benchmark_runner import run_benchmark_async, sync_evaluations_from_files, dashboard_logger

class EvaluationMonitorComponent:
    """Component for monitoring active evaluations."""
    
    def render(self):
        """Render the evaluation monitor component."""
        # Create a placeholder for notifications at the very top of the page
        notification_placeholder = st.empty()
        
        dashboard_logger.info("Rendering evaluation monitor component")
        
        # Debug information about current session state
        print(f"Current evaluations in session state: {len(st.session_state.evaluations)}")
        for i, eval_config in enumerate(st.session_state.evaluations):
            print(f"Evaluation {i+1}: ID={eval_config['id']}, Name={eval_config['name']}, Status={eval_config['status']}")
        
        # Sync evaluation statuses from files
        sync_evaluations_from_files()
        
        # Initialize notification variables in session state if they don't exist
        if 'notifications' not in st.session_state:
            st.session_state.notifications = []
        if 'notification_history' not in st.session_state:
            st.session_state.notification_history = []
        if 'last_status_check' not in st.session_state:
            st.session_state.last_status_check = {}
        if 'show_notification_sound' not in st.session_state:
            st.session_state.show_notification_sound = True
            
        # Check for status changes and create notifications
        for eval_config in st.session_state.evaluations:
            eval_id = eval_config.get("id")
            current_status = eval_config.get("status")
            
            # Skip if we've already checked this evaluation or if it's not in a terminal state
            if eval_id not in st.session_state.last_status_check:
                st.session_state.last_status_check[eval_id] = current_status
            elif st.session_state.last_status_check[eval_id] != current_status:
                # Status has changed
                if current_status in ["completed", "failed"]:
                    # Create a new notification
                    notification = {
                        "id": eval_id,
                        "name": eval_config.get("name", "Unknown"),
                        "status": current_status,
                        "timestamp": time.time(),
                        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "dismissed": False
                    }
                    
                    # Add to active notifications (limit to 3 most recent)
                    st.session_state.notifications.append(notification)
                    if len(st.session_state.notifications) > 3:
                        st.session_state.notifications = st.session_state.notifications[-3:]
                    
                    # Add to notification history
                    st.session_state.notification_history.append(notification.copy())
                    # Keep history to most recent 50 notifications
                    if len(st.session_state.notification_history) > 50:
                        st.session_state.notification_history = st.session_state.notification_history[-50:]
                        
                    dashboard_logger.info(f"Created notification for evaluation {eval_id}: {current_status}")
                
                # Update the stored status
                st.session_state.last_status_check[eval_id] = current_status
                
        # Display notifications banner at the top of the page
        notification_container = st.container()
        with notification_container:
            current_time = time.time()
            active_notifications = []
            
            # Add sound alerts
            if st.session_state.notifications and st.session_state.show_notification_sound:
                # Embed audio for notification sounds
                # Success sound for completed evaluations
                success_audio = """
                <audio id="notification-success" autoplay>
                  <source src="data:audio/wav;base64,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AOA0QAgIgAEiMurv/s/+36GxwZBYDAqZVbe/3d/v9BoIDA6IAL//9/v/91+/8///+rv/f/u+hsDwGGAwBAYIDE1MrOy/3X+7/v9LDoJAhcIiq///9/bDIwDA0MAqGgANj/7/+/jYMS9DtklMSxhoCr7///rIUi4CBghgBihRW/f/+//+7wSDRUBxB//+r//9u//3/X//r/f/XgPGRobGhcDgoNS5K///3/+//7gHiIhKn/3////e4gZGQwMzXX/+////2hAK///6v/+v/dDKK4TGhgXFIIwEAA2J0r/3u/7v/vwB8NDocAQeCqpbv/99///2w6E4mAQAP/jYMTEDrElKS1hgMJvr/3//9Z/7//+//f/aCoREYwHE4GCQ0Ufpf//3/+/98ECLDf/9//9/9gDA8EAcRGRoWD/3//9//9wCh1//f/f//ZAQVHRoZEoEhwu/d//93/7/wDBCO//v//3/7CIAQAD/++/3/9/oAgF//f//2W/f/dCoGX///r//+7AwCAM//f/7u/+nXABB4HCAqMDYpP/jYMTIDrElNS1hgKIu7q+3utyu7rnTAAMANE3/X3d3dlGzK79lXd1lmWbMrL97OxcKy3r+7u6zMu7qrurLO7LOyqrMszKqsqqzMzurszKqMz+7Ky7qqsyzcf//+/92BYA0f//9///0JQBE3////9/8KhPSqZVVmd2W/72u7HQjDBUACovLqrVnKr93/s+/szuzuwKAv/+3/jYMTMDrEdJSlhgMJCCgBb/9/+++9wEBYDAyBu/////91ABgMMCEAKq//v//f+AwER///f//72hoAzAsCQQDojMqru7P/f//33ZmZVXdmVXZVVXZVW7OquzLN3Lv//7srMsqs7uzKquzKzLKqqyu3X+yVXZXuaA8BgUBwADCRNqyqzsf7K7LMq7Luzs7KqKCgEBcZl12d2Z2Zl3aCA8P/jYMTUDpEFKS1hgMI6Cwg/v3+7///+gRDAwQCp///3//+wFAf//X//93wQAAAGAMCgIAREZVdlf//3//+6uyrv7v7qqqqqqqruy7s7Mu//3Zlft/Z2VVXZ3X3Z2VVVS1Vv////ut/b939ldtf/9/d//++wYB0jCZd//9//7/gYB5//v//3+8DwIAAEBA0BwKkYlWszO7M7L/d/jYMTaDnEFKS1hgKI33f2dn5gNCAHCp//+r//+1AuBaRmV3Z2XdlWfdnd3Z2X5mZnZYDRJmZmdnZZZ1zMzLMyqzuzLd/f//d3+3d3ZZ///+/9/+xQHjgRH3///9/3gQA3f/+//f+wCAwAAcCAxGRoZFxs/6//+v//uwEB5///+//d+woBAAIDCoPiowHFZEAABxYD//9//jYMThDlEFIS1hgMI/9/ugqL///3/7/7QaCA6+//3///2OhzGBYFAKVdmXdnd2d2ZmZlmZnZmd3Zl3ZWXZmZmZl2ZmdlldZnZlmZlmZlmZd3ZfvZ92ZdZ33//f93+//v/3e3//6+//9u5oHBoJAQFxcXFRlVu/v7/v/+sDY0JgCEBgJjcv////r//uUEwoDwABsXC4+f/2//7/jYMTqDvEFHS1hgMI/7/wBBcGQOGAMBEYGBQaJv+r//f//dwQDAUBgUIwZ+///v//91EQgQFIrL77urKrMvvuyqsy77urKqsq/uzqqquzLs7qrLu//3d2Xfu//+/9/+73/v/76v3/+t0KiUxMRkXbLsUB42JgBBoHBUAggBEQMCEbGJf9f//+/37ASD4GCIj///7/3/jYMTtDpEFHS1hgKIv7/wPAsBAQGAJCIsNCMGfv///f//9wKA7/9///3/uGAgNDxr7//9/9+3/RYAB8//f/+//3AOCJ///+//++BQX///v//+8FwRDAwGAIiNDgwJwAFJXZdldl3d3d32dmZXZV31Z9mZX9kNBYADJHZmdm////d93+6W7/v/+7/jYMTxDlEFGSxhgKI373/3YAIRFxIAAAFBkYGh5Vf/v/f//77gVAwAA6aGBgb/X////8g8EQ8aGxge//3+///2CGIBMBAHCQ4Lrb//3//9nXDQy+///+v//vgHAyKjA0PDYkPnf/+v//+/IBwAEBcMAoZFhIUFCf7//3///AKi4KCYKDAvMq//3//+/2AKDIMi4s+/jYMT2DjEFGS1hgMI//f/3//+hYCh///f/+/4Cg7///X//93hhP//+/7+/3gED//33///dA+DMQGI2IgCBYKDQ1/X////33gPDsaA4MA4NCc6//v/7//2gWGAMEApLDX/+v//9sEA8C43Gv///7///4Gg+v/f/+//bDQWEBgZERQPjqysqqrKuyqrNmV3ZmZYDQGP/jYMT7DfEFFSxhgKI8gGAILDIzKqrszLsy/uzuzLd2fZmZZmZmZmWZnfd2d3d2ZdmZlmZmZ3d2ZmZmeaAIBACBQ3MzLtmVlmdl2ZdlVlmZmd3Z2ZXZmdmZmZnZVVWZ2VVZmZlmV2Z2dlVVXZnZVVZWVVZnZ2VVZmZZmZ2VXZnZVdlVlXZmZnd2ZdmVd2V3ZmZlmdnZnZmf/jYMUBDjEFFSxhgKI2ZdmZmVVZlmZmZlVVZmZVVVVVVlVZVZmZnZVVdmZmZmZ3d3d2ZmZmd3dlVVVVVVVVmd3dVVVVVVVVVVXZnZVVVVVVVVVVV2ZVVVVVmZnZVVVVVVVmZmZVVVZmZVVVVVZmZmZmdmZlVVVVVlVVVmZVVVVVVVZmZVVVmZmZlZlVVVVmZVVVVVVVVVWZVVVmZVVVVVVVVV</source>
                </audio>
                <!-- Failure sound for failed evaluations -->
                <audio id="notification-failure" autoplay>
                  <source src="data:audio/wav;base64,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BoYAYSN////+xX1DUMEgKCAmYGgiYAgKYCAMfIwCA0YAAaYDgIKgCp///9///JsZGgkYFhUKCRj+EP/jYMRGDvCVbXsPMHIJA0wIAMDgKYOgGYDAIKgIo////++MIgsARMHoVQQOMVAFBIQMFQGMAwFAIDMDwHNTYH/+////JQYXgQYCgUEiYJBgwSA8wSAMTQBAQwAA4yWBUGD3//f//5NeGQaDwIBBh2FAgB2//f/+/5CBSYYA8RAGGu///v//+UKB5gwC5iYGhgiBJEAq//9//v/yRP/jYMRTDuCVZ+wyQpLAYCBQYDgaExQAQu/////dUxJgwBBUVAiQpMCQ2MBgjBAEGDwBAID4EDcvAkOv//f/+pxRYNGFwSCYUApf/9///5s/mDw3mGoCCQZMEgMMHwSMBASAQw//v//++s+hhxhCM4MFVf//7f//lSxhGBQXAQwZCz//3///ykNGaQLmAwWGIQIARf//+///lNRgeP/jYMRaDuCFXXsPSPIFBpgkBwmAb//7v//+sXGQaCTB0FDLyAwwUGAHCgFQEaKAOBQA3///f/zhBBgABABCMCgPMC/////+l/91//MAQGAwHzT///v//1GsUDQYYFAuMgDjUOBsVJMEgHAQVFP//f//6wAFTAUHTK8JQIACoCgICgMCxABAODABMCQMA1v///8nQKBYdBYwCBQICgDAJgMjA0P/jYMRiDtCFV+wywpKHQgMCg0MAFMAwLA0D4LCIDQEq//9///+ZVQBgOHRkiGhgECJgWAQMAZl///7f//kw6AEBBQYBrv//3//7FRkOAhgYBAGA4wZCgwAQ0DBQNDBsEjIwLAADzG///+//+URZgMCZgEBgcCLu////7/LUxZgwkAwwFAVf/d///kIECgGMAAsMAQfAQM7///jYMRrDvBxTXsPGTI93////v+ZLjBYCQcAgKYEA+YcgUEQElL///f//65XFAuAgEF1////+nIxJhwMGTOZlnZ3/d3d+ZXdmZmZlnZnZdZl2YCgUBQgMvMzOzuz/uzvu7Kv7MzLsysyqzO7Ory7MrMqqzKrOzK7M7Lsy7uyrsyu7KzOzLMzMrurMzMzO7OzKrMruru7LuzLu/jYMR1DrB1N+wyYk+zLuyyuzLs7Lu7KzLu7M77uzLuzu7uy7szLu7uy7MrKrsyqrOzKzKrs7Muyyru7Lu7Mu7uysyqrOzuzKqqzKvLO/MzLMqqzKqzu7LsyqzMzMzMzOzMzLuqsqq7Kvuyu7v7u7szLs7s7MzMzs7szMruyqysyrsrMzM7MzLM7MuzOzLMzMzM7MzsrOzLuqqqsysyz/jYMR+DnB1J1hjQpMsrszMszMzMzMzMzMzuzMzM7MzM7MzMzMzO7MzM7MzO7MzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM7uzOzMzO7M7OzMzM7MzOzszM7uzMzMzMzMzMzMzMzMzMzM7MzMzMzMzMzMzMzMzMzM7MzMzMzMzMzMzMzMzMzMzMzM7MzOzMzMzMzMzMzM</source>
                </audio>
                """
                
                # Add different sounds based on notification status
                for notification in st.session_state.notifications:
                    if notification.get("status") == "completed" and not notification.get("sound_played"):
                        st.markdown(success_audio, unsafe_allow_html=True)
                        notification["sound_played"] = True
                    elif notification.get("status") == "failed" and not notification.get("sound_played"):
                        st.markdown(failure_audio, unsafe_allow_html=True)
                        notification["sound_played"] = True
            
            # Process active notifications (limit to 3 most recent)
            current_time = time.time()
            active_notifications = []
            
            for notification in st.session_state.notifications:
                # Skip if manually dismissed
                if notification.get("dismissed", False):
                    continue
                    
                # Only show notifications that are less than 3 seconds old
                if current_time - notification["timestamp"] < 3:
                    active_notifications.append(notification)
                    
                    # Choose styling based on status
                    if notification["status"] == "completed":
                        banner_style = "background-color: rgba(0, 255, 0, 0.2); color: darkgreen; padding: 10px; border-radius: 5px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;"
                        icon = "✅"
                    else:  # failed
                        banner_style = "background-color: rgba(255, 0, 0, 0.2); color: darkred; padding: 10px; border-radius: 5px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;"
                        icon = "❌"
                    
                    # Display the notification with close button and clickable content
                    col1, col2 = st.columns([10, 1])
                    with col1:
                        # Create a clickable banner
                        if st.button(f"{icon} Evaluation **{notification['name']}** {notification['status']}!", 
                                    key=f"notify_{notification['id']}_{int(notification['timestamp'])}"):
                            # Find this evaluation in the session state
                            for i, eval_config in enumerate(st.session_state.evaluations):
                                if eval_config.get("id") == notification["id"]:
                                    # Set session state to highlight this evaluation
                                    st.session_state["highlight_eval_id"] = notification["id"]
                                    dashboard_logger.info(f"Navigating to evaluation details for {notification['id']}")
                                    break
                    
                    with col2:
                        # Add dismiss button
                        if st.button("×", key=f"close_{notification['id']}_{int(notification['timestamp'])}"):
                            notification["dismissed"] = True
                            dashboard_logger.info(f"Manually dismissed notification for {notification['id']}")
            
            # Keep only the active notifications
            st.session_state.notifications = [n for n in st.session_state.notifications if not n.get("dismissed", False) and current_time - n["timestamp"] < 3]
            
            # Show notification history toggle
            if st.session_state.notification_history:
                with st.expander("📢 Notification History", expanded=False):
                    # Option to enable/disable sound
                    st.checkbox("Enable notification sounds", value=st.session_state.show_notification_sound, 
                                key="sound_toggle", on_change=lambda: setattr(st.session_state, 'show_notification_sound', 
                                                                            not st.session_state.show_notification_sound))
                    
                    # Display history as a table
                    history_data = []
                    for notification in reversed(st.session_state.notification_history):
                        history_data.append({
                            "Time": notification["datetime"],
                            "Evaluation": notification["name"],
                            "Status": notification["status"].capitalize(),
                            "ID": notification["id"]
                        })
                        
                    if history_data:
                        history_df = pd.DataFrame(history_data)
                        
                        # Add interactive options
                        selected_history = st.selectbox(
                            "Select notification to view details",
                            options=range(len(history_data)),
                            format_func=lambda i: f"{history_data[i]['Time']} - {history_data[i]['Evaluation']} ({history_data[i]['Status']})"
                        )
                        
                        # Display the history table
                        st.dataframe(history_df, use_container_width=True)
                        
                        # Action buttons for selected notification
                        col1, col2 = st.columns(2)
                        with col1:
                            # Navigate to the selected evaluation
                            if st.button("Go to Evaluation", key="goto_history_eval"):
                                eval_id = history_data[selected_history]["ID"]
                                st.session_state.highlight_eval_id = eval_id
                                dashboard_logger.info(f"Navigating to evaluation {eval_id} from history")
                                st.rerun()
                        
                        with col2:
                            # Clear history button
                            if st.button("Clear History"):
                                st.session_state.notification_history = []
                                dashboard_logger.info("Cleared notification history")
                                st.rerun()
            
        # Use Streamlit's built-in auto-refresh functionality
        # This creates a small container with a "Refreshing..." spinner
        # that triggers a full page refresh on the interval
        with st.empty():
            # Only show if we have active evaluations
            if any(e.get('status') in ['in-progress', 'running'] for e in st.session_state.evaluations):
                auto_refresh = st.empty()
                with auto_refresh.container():
                    st.write("⟳ Auto-refreshing...")
                    # Use Streamlit's built-in rerun mechanism
                    time.sleep(5)  # Wait 5 seconds before refreshing
                    st.rerun()  # This will rerun the entire app
                    
        # Track and display last refresh time
        current_time = time.time()
        if 'last_refresh_time' not in st.session_state:
            st.session_state.last_refresh_time = current_time
            
        # Calculate time since last refresh
        time_since_refresh = current_time - st.session_state.last_refresh_time
        st.session_state.last_refresh_time = current_time
        
        # Log refresh event
        dashboard_logger.info(f"Refreshed evaluation statuses (time since last refresh: {time_since_refresh:.1f}s)")
            
        # Add a UI indicator for the log file location
        from ..utils.constants import PROJECT_ROOT
        log_dir = os.path.join(PROJECT_ROOT, 'logs')
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
                # Highlight the evaluation if it matches the one clicked in a notification
                highlight_style = ""
                if "highlight_eval_id" in st.session_state and st.session_state.highlight_eval_id == eval_config["id"]:
                    highlight_style = "border: 2px solid #FFA500; background-color: rgba(255, 165, 0, 0.1); border-radius: 5px; padding: 10px;"
                    # Clear the highlight after showing it once
                    st.session_state.highlight_eval_id = None
                
                with st.container():
                    if highlight_style:
                        st.markdown(f'<div style="{highlight_style}">', unsafe_allow_html=True)
                    
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
                
                # Close the highlight div if it was opened
                if "highlight_eval_id" in st.session_state and st.session_state.highlight_eval_id == eval_config["id"]:
                    st.markdown('</div>', unsafe_allow_html=True)
                
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
            from ..utils.constants import PROJECT_ROOT
            log_dir = os.path.join(PROJECT_ROOT, 'logs')
            st.info(f"Check logs in: {log_dir}")
            
        if failed_evals:
            for name, error in failed_evals:
                st.error(f"Failed to start '{name}': {error}")
                
        # Force refresh of UI state
        if started_evals:
            sync_evaluations_from_files()