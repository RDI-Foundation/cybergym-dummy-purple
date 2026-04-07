import asyncio
import base64

from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, FilePart, FileWithBytes, Message, Part
from a2a.utils import get_message_text, new_agent_text_message

from messenger import Messenger


class Agent:
    def __init__(self):
        self.messenger = Messenger()
        # Initialize other state here
        self._challenge_received = False
        self._test_result: asyncio.Queue[dict] = asyncio.Queue()

    async def run(self, message: Message, updater: TaskUpdater) -> None:
        """Implement your agent logic here.

        Args:
            message: The incoming message
            updater: Report progress (update_status) and results (add_artifact)

        Use self.messenger.talk_to_agent(message, url) to call other agents.
        """
        input_text = get_message_text(message)

        # Replace this example code with your agent logic
        # Second call: green is delivering the PoC test result
        if self._challenge_received:
            result = _get_data_part(message)
            await self._test_result.put(result or {})
            return

        # First call: green is sending the challenge files
        file_parts = [part for part in message.parts if isinstance(part.root, FilePart)]

        # No files means this isn't a real challenge (e.g. conformance test) — exit early
        if not file_parts:
            await updater.reject(new_agent_text_message("no challenge files received"))
            return

        self._challenge_received = True

        ctx = message.context_id
        print(f"[{ctx}] Received challenge:", input_text)

        # Show brief info about received challenge files
        for part in file_parts:
            f = part.root.file
            if isinstance(f, FileWithBytes):
                raw = base64.b64decode(f.bytes)
                print(f"[{ctx}]   {f.name}: {len(raw)} bytes ({f.mime_type})")
                if f.name and (f.name.endswith(".txt") or f.name.endswith(".md")):
                    print(raw.decode("utf-8", errors="replace"))

        poc_bytes = b"hi from dummy agent\n"

        # Test the validation workflow with an dummy PoC file
        print(f"[{ctx}] Testing validation workflow with dummy PoC...")
        await updater.requires_input(updater.new_agent_message(parts=[
            Part(root=DataPart(data={"action": "test_vulnerable"})),
            Part(root=FilePart(
                file=FileWithBytes(
                    bytes=base64.b64encode(poc_bytes).decode("ascii"),
                    name="poc",
                    mime_type="application/octet-stream",
                )
            )),
        ]))

        # Wait for green's test result
        test_result = await self._test_result.get()
        print(f"[{ctx}] Validation result:", test_result)

        # Submit the dummy file as the final PoC artifact
        await updater.add_artifact(
            parts=[Part(root=FilePart(
                file=FileWithBytes(
                    bytes=base64.b64encode(poc_bytes).decode("ascii"),
                    name="poc",
                    mime_type="application/octet-stream",
                )
            ))],
            name="poc",
        )


def _get_data_part(message: Message) -> dict | None:
    for part in message.parts:
        if isinstance(part.root, DataPart):
            return part.root.data
    return None
