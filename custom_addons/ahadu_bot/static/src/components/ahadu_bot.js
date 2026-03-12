/** @odoo-module **/

import { Component, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc"; // 1. IMPORT RPC DIRECTLY

export class AhaduBotSystray extends Component {
  setup() {
    // 2. REMOVED: this.rpc = useService("rpc");
    this.actionService = useService("action");
    this.inputRef = useRef("inputRef");

    this.state = useState({
      isOpen: false,
      isLoading: false,
      inputValue: "",
      messages: [
        {
          id: 0,
          type: "bot",
          text: "Hello! I am your Ahadu Assistant. How can I help you today?",
        },
      ],
    });
  }

  toggleBot() {
    this.state.isOpen = !this.state.isOpen;
    if (this.state.isOpen) {
      setTimeout(() => {
        if (this.inputRef.el) this.inputRef.el.focus();
      }, 100);
    }
  }

  async sendMessage() {
    const text = this.state.inputValue.trim();
    if (!text) return;

    // Add User Message
    const msgId = new Date().getTime();
    this.state.messages.push({ id: msgId, type: "user", text: text });
    this.state.inputValue = "";
    this.state.isLoading = true;
    this.scrollToBottom();

    try {
      // 3. USE THE IMPORTED RPC DIRECTLY INSTEAD OF this.rpc
      const response = await rpc("/ahadu_bot/chat", { message: text });

      // Add Bot Message
      this.state.messages.push({
        id: msgId + 1,
        type: "bot",
        text: response.text,
      });
      this.state.isLoading = false;
      this.scrollToBottom();

      // Execute Actions if returned
      if (response.action) {
        // Little delay so user reads the message before popup appears
        setTimeout(() => {
          this.actionService.doAction(response.action);
          this.state.isOpen = false; // Close bot when action opens
        }, 1500);
      } else if (response.url) {
        setTimeout(() => {
          window.open(response.url, "_blank");
        }, 1500);
      }
    } catch (error) {
      this.state.isLoading = false;
      this.state.messages.push({
        id: msgId + 1,
        type: "bot",
        text: "Sorry, I am having trouble connecting to the server.",
      });
    }
  }

  scrollToBottom() {
    setTimeout(() => {
      const container = document.getElementById("ahadu_bot_messages");
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    }, 50);
  }
}

AhaduBotSystray.template = "ahadu_bot.SystrayItem";

// Add to the Systray
registry.category("systray").add(
  "ahadu_bot.AhaduBotSystray",
  {
    Component: AhaduBotSystray,
  },
  { sequence: 25 },
);
