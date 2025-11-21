import asyncio
import logging
import json
import grpc

from cline_core import ClineInstance
from cline_core.proto.cline.common_pb2 import Metadata
from cline_core.proto.cline.task_pb2 import NewTaskRequest
from cline_core.proto.cline import task_pb2_grpc
from cline_core.proto.cline.state_pb2 import Settings, PlanActMode, AutoApprovalSettings, AutoApprovalActions, TogglePlanActModeRequest
from cline_core.proto.cline.state_pb2_grpc import StateServiceStub

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    with ClineInstance.with_available_ports() as instance:
        with grpc.insecure_channel(instance.address) as channel:
            current_mode = PlanActMode.ACT

            response = task_pb2_grpc.TaskServiceStub(channel).newTask(NewTaskRequest(
                metadata=Metadata(),
                text="Create a simple hello world Python script and save it as hello.py",
                task_settings=Settings(
                    auto_approval_settings=AutoApprovalSettings(
                        actions=AutoApprovalActions(
                            read_files=True,
                            edit_files=True,
                            execute_safe_commands=True,
                        )
                    ),
                    mode=current_mode
                )
            ))

            logger.info(f"✅ Task created successfully with ID: {response.value}")

            state_stub = StateServiceStub(channel)
            state_responses = state_stub.subscribeToState(Metadata())

            update_count = 0
            found_completion = False

            conversation_history_index = -2

            logger.info("\nContinuing to monitor state updates...")

            for state_response in state_responses:
                if found_completion:
                    break

                state_json = json.loads(state_response.state_json)

                logger.info(f"mode {state_json.get('mode')}")

                new_mode = PlanActMode.ACT if state_json.get('mode') == "act" else PlanActMode.PLAN

                if new_mode != current_mode:
                    mode_response = state_stub.togglePlanActModeProto(TogglePlanActModeRequest(
                        metadata=Metadata(),
                        mode=new_mode
                    ))
                    current_mode = new_mode
                    logger.info(f"✓ Mode toggled to {current_mode}, response: {mode_response}")

                for message in state_json.get('clineMessages'):
                    if message['conversationHistoryIndex'] < conversation_history_index:
                        continue

                    should_display = True

                    if message.get("partial"):
                        # Exception: display if type=say, text="", say="text"
                        if message["type"] == "say" and message["text"] == "" and message["say"] == "text":
                            should_display = True
                        else:
                            should_display = False

                    if message.get("say") == "completion_result":
                        found_completion = True
                        logger.info('COMPLETE', message.get('text'))
                        break

                    if should_display:
                        logger.info(f"Type: {message['type']}. Say: {message.get('say')}: {message.get('text')}")

                    conversation_history_index = message['conversationHistoryIndex']

                update_count += 1

if __name__ == "__main__":
    asyncio.run(main())
