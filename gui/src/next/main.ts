// The rebuilt GUI's entry (WP-2215), served at /next beside today's page until
// the swap (WP-2214 § The swap). `app.css` first: the tokens and the registers
// the imported panels are drawn with; `next.css` then draws the frame, and
// `fonts.css` declares the faces it sets, which only this page loads.
import { mount } from "svelte";

import "../app.css";
import "./next.css";
import "./fonts.css";
import Frame from "./Frame.svelte";

export default mount(Frame, { target: document.getElementById("app")! });
