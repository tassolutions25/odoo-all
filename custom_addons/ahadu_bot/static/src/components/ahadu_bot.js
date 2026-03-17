/** @odoo-module **/

import { Component, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc"; // 1. Imported rpc directly (Fixes White Screen)

export class AhaduBotSystray extends Component {
  static template = "ahadu_bot.SystrayItem"; // Moved template inside the class
  static props = { "*": true }; // 2. Added wildcard props (Fixes the Owl Dev Warning)

  setup() {
    // this.rpc = useService("rpc"); <--- REMOVED: This was causing the crash
    this.actionService = useService("action");
    this.inputRef = useRef("inputRef");

    this.state = useState({
      isOpen: false,
      inputValue: "",
      messages: [
        {
          id: 0,
          type: "bot",
          text: "Hello! I am your Ahadu Assistant. Type what you are looking for (e.g., 'Leave', 'Payslip', 'Promotions', 'Dashboards').",
        },
      ],
    });
  }

  toggleBot() {
    this.state.isOpen = !this.state.isOpen;
    if (this.state.isOpen) {
      setTimeout(() => {
        if (this.inputRef.el) this.inputRef.el.focus();
        this.scrollToBottom();
      }, 100);
    }
  }

  async sendMessage() {
    const text = this.state.inputValue.trim();
    if (!text) return;

    // 1. Add User Message to screen
    const msgId = new Date().getTime();
    this.state.messages.push({ id: msgId, type: "user", text: text });
    this.state.inputValue = "";
    this.scrollToBottom();

    try {
      // 2. Send message to Python Controller using the imported rpc function
      const response = await rpc("/ahadu_bot/chat", { message: text });

      // 3. Add Bot Response to screen
      this.state.messages.push({
        id: msgId + 1,
        type: "bot",
        text: response.text,
      });
      this.scrollToBottom();

      // 4. If python returned an action, open it automatically!
      if (response.action) {
        setTimeout(() => {
          this.actionService.doAction(response.action);
          this.state.isOpen = false; // Close chat window
        }, 1500); // 1.5 second delay so user can read the text
      }
      // 5. If python returned a URL, redirect to it!
      else if (response.url) {
        setTimeout(() => {
          window.location.href = response.url;
        }, 1500);
      }
    } catch (error) {
      this.state.messages.push({
        id: msgId + 1,
        type: "bot",
        text: "Sorry, I lost connection to the server.",
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

// Adds the bot to the top menu bar in Odoo
registry.category("systray").add(
  "ahadu_bot.AhaduBotSystray",
  {
    Component: AhaduBotSystray,
  },
  { sequence: 25 },
);
