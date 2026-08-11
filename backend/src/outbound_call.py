"""Outbound Call Dispatcher for LiveKit Voice Agent.

Allows triggering outbound SIP calls or room dispatches for line phone integration without Twilio.
"""

import argparse
import asyncio
import contextlib
import json
import os
import sys

from dotenv import load_dotenv
from livekit import api

# Load local environment variables
load_dotenv(".env.local")


async def create_outbound_sip_call(
    phone_number: str,
    sip_trunk_id: str | None = None,
    room_name: str | None = None,
    target_name: str | None = None,
):
    """Dispatch an outbound SIP call using LiveKit API.

    Args:
        phone_number: Destination phone number (e.g. +919876543210).
        sip_trunk_id: LiveKit SIP Outbound Trunk ID.
        room_name: Name of room to create for this call.
        target_name: Target caller's name for greeting (e.g. Ramesh, Krishna).
    """
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    trunk_id = sip_trunk_id or os.getenv("LIVEKIT_SIP_TRUNK_ID")
    caller_name = target_name or os.getenv("OUTBOUND_CALLER_NAME", "Krishna")

    if not url or not api_key or not api_secret:
        print(
            "ERROR: Missing LIVEKIT_URL, LIVEKIT_API_KEY, or LIVEKIT_API_SECRET in environment.",
            file=sys.stderr,
        )
        sys.exit(1)

    lk_api = api.LiveKitAPI(url=url, api_key=api_key, api_secret=api_secret)

    try:
        room = room_name or f"outbound-call-{int(asyncio.get_event_loop().time())}"
        print(f"[*] Creating outbound room on LiveKit: '{room}' for '{caller_name}'...")

        room_meta = json.dumps({"target_name": caller_name})

        # Ensure room exists on LiveKit Cloud with metadata
        with contextlib.suppress(Exception):
            await lk_api.room.create_room(
                api.CreateRoomRequest(name=room, metadata=room_meta)
            )

        # Dispatch agent "my-agent" into this room so it joins and speaks upon connection
        with contextlib.suppress(Exception):
            await lk_api.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name="my-agent", room=room, metadata=room_meta
                )
            )
            print(f"[*] Dispatched agent 'my-agent' to room '{room}'...")

        if trunk_id:
            print(
                f"[*] Attempting SIP call to {phone_number} via trunk '{trunk_id}'..."
            )
            try:
                sip_req = api.CreateSIPParticipantRequest(
                    sip_trunk_id=trunk_id,
                    sip_call_to=phone_number,
                    room_name=room,
                    participant_identity=f"phone_{phone_number.replace('+', '')}",
                    participant_name="Caller (Phone)",
                )
                participant = await lk_api.sip.create_sip_participant(sip_req)
                print(
                    f"[+] SIP Outbound call initiated successfully! Participant ID: {participant.participant_id}"
                )
            except Exception as err:
                print("\n[!] SIP CALL ERROR:")
                print(
                    f"    The SIP Trunk ID '{trunk_id}' was not found or is not active in your LiveKit Cloud project."
                )
                print(f"    Details: {err}")
                print("\n[*] FALLBACK TO ROOM DISPATCH MODE:")
                print(
                    f"    Created room: '{room}' — You can test the outbound AI voice flow directly"
                )
                print(
                    "    by connecting to this room from your Frontend / WebRTC client!"
                )
                print(
                    "\n    (To fix real phone calls: Go to https://cloud.livekit.io -> Telephony -> SIP Outbound,"
                )
                print(
                    "     create a SIP Outbound Trunk, and update LIVEKIT_SIP_TRUNK_ID in .env.local)"
                )
        else:
            print(
                "[*] LIVEKIT_SIP_TRUNK_ID not set. Room created for WebRTC/Line Phone client testing."
            )
            print(
                f"[+] Room Name: '{room}' — Connect frontend or SIP client to test outbound flow."
            )

    finally:
        await lk_api.aclose()


def main():
    parser = argparse.ArgumentParser(
        description="Trigger Outbound Call / Line Phone Dispatch via LiveKit"
    )
    default_phone = os.getenv("OUTBOUND_CALLER_ID", "+919876543210")
    default_name = os.getenv("OUTBOUND_CALLER_NAME", "Krishna")
    parser.add_argument(
        "--phone",
        type=str,
        default=default_phone,
        help=f"Target phone number for SIP call (default: {default_phone})",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=default_name,
        help=f"Target caller's name for greeting (default: {default_name})",
    )
    parser.add_argument(
        "--trunk",
        type=str,
        default=None,
        help="SIP Outbound Trunk ID (optional)",
    )
    parser.add_argument(
        "--room",
        type=str,
        default=None,
        help="Room name (optional)",
    )
    args = parser.parse_args()

    asyncio.run(
        create_outbound_sip_call(
            phone_number=args.phone,
            sip_trunk_id=args.trunk,
            room_name=args.room,
            target_name=args.name,
        )
    )


if __name__ == "__main__":
    main()
