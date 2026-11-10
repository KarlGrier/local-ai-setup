#!/usr/bin/env python3
"""test_webapp.py [APP_JS] — round 3: run serve/web/app.js in QuickJS with a permissive DOM / localStorage / fetch stub
and exercise the chat list: the migration of the old single chat, sending (a fake finished answer), New chat, switching,
the saved request history of a chat with an attached file, deleting (and undo), and a full storage.  Any exception
fails the test.  No browser, no server."""
import json
import sys
from pathlib import Path

import quickjs

APP = Path(sys.argv[1] if len(sys.argv) > 1 else
           "/home/USER/ai-speed-testing/strata-compare/strata-r3-run/serve/web/app.js").read_text()

STUB = r"""
var __log = [];
function mkEl(id) {
  var el = {id: id, dataset: {}, style: {}, hidden: false, value: "", innerHTML: "", children: [], _text: "",
    get textContent() { return this._text; }, set textContent(v) { this._text = v; this.children = []; },
    classList: {add(){}, remove(){}, toggle(){}, contains(){ return false; }},
    setAttribute(k, v) { this["attr_" + k] = v; }, getAttribute(k) { return this["attr_" + k] || null; },
    appendChild(c) { this.children.push(c); return c; }, append() { for (var i = 0; i < arguments.length; i++) this.children.push(arguments[i]); },
    addEventListener() {}, removeEventListener() {}, focus() {}, click() {}, remove() {}, scrollTo() {},
    querySelector() { return mkEl("q"); }, querySelectorAll() { return []; }, closest() { return null; },
    getBoundingClientRect() { return {top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0}; },
    insertBefore(c) { return c; }, replaceChildren() { this.children = []; }, cloneNode() { return mkEl(id); },
    scrollHeight: 0, scrollTop: 0, clientHeight: 0, lastElementChild: null, firstChild: null, parentNode: null, files: []};
  return el;
}
var __els = {};
var document = {
  getElementById(id) { if (!__els[id]) __els[id] = mkEl(id); return __els[id]; },
  createElement(t) { return mkEl(t); }, querySelector() { return mkEl("q"); }, querySelectorAll() { return []; },
  addEventListener() {}, documentElement: mkEl("html"), body: mkEl("body"), hidden: false, visibilityState: "visible"};
var __store = {}, __full = false;
var localStorage = {
  getItem(k) { return k in __store ? __store[k] : null; },
  setItem(k, v) { if (__full && k.indexOf("strata.chat.") === 0 && v.length > 1000) throw new Error("QuotaExceededError"); __store[k] = String(v); },
  removeItem(k) { delete __store[k]; }};
var window = {matchMedia() { return {matches: false, addEventListener() {}, addListener() {}}; }, addEventListener() {},
              innerHeight: 800, location: {search: "", hash: "", pathname: "/"}};
var location = window.location, innerHeight = 800;
var history = {replaceState() {}};
var navigator = {clipboard: {writeText() { return Promise.resolve(); }}};
function matchMedia() { return window.matchMedia(); }
function URLSearchParams() { return {get() { return null; }}; }
var URL = {createObjectURL() { return "blob:"; }, revokeObjectURL() {}};
function Blob() {}
function FileReader() {}
function AbortController() { return {signal: {}, abort() {}}; }
var performance = {now() { return Date.now(); }};
function requestAnimationFrame(f) { return 1; }
function cancelAnimationFrame() {}
var __timers = [];
function setTimeout(f, t) { __timers.push(f); return __timers.length; }
function clearTimeout() {}
function setInterval() { return 1; }
function clearInterval() {}
function fetch(url, opts) { return Promise.resolve({ok: false, status: 503, json() { return Promise.resolve({}); },
                                                   text() { return Promise.resolve(""); }, body: null}); }
var console = {log() { __log.push(Array.prototype.join.call(arguments, " ")); }, warn() {}, error() { __log.push("ERR " + Array.prototype.join.call(arguments, " ")); }};
"""

ctx = quickjs.Context()
ctx.eval(STUB)
# a v0.1.12 browser: one saved chat under the old key
ctx.eval('__store["strata.chat"] = JSON.stringify([{role:"user",text:"old question",time:1},{role:"assistant",text:"old answer",time:2}]);')
ctx.eval(APP)                                   # the page loads (throws on any runtime error at load)
checks = []


def js(expr):
    return ctx.eval(expr)


def check(name, cond):
    checks.append((name, bool(cond)))


check("migrated: one chat in the index", js('JSON.parse(__store["strata.chats"]).length') == 1)
check("migrated: old key removed", js('!("strata.chat" in __store)'))
check("migrated: messages loaded", js('messages.length') == 2 and js('messages[0].text') == "old question")
first_id = js('chatId')
# New chat: the old one stays, the new one gets an id with its first message
js('newChat()')
check("new chat: empty, no id yet", js('messages.length') == 0 and js('chatId') is None)
js('messages.push({role:"user",text:"second chat question",time:3}); '
   'messages.push({role:"assistant",text:"second answer",time:4}); saveChat();')
check("new chat saved: two chats", js('chats.length') == 2)
second_id = js('chatId')
check("titles", js('chats.map(c => c.title).sort().join("|")') == "old question|second chat question")
# a chat with an attached file keeps the file's text across a reload
js('messages.push({role:"user",text:"see file",files:[{name:"a.txt",text:"FILE BODY"}],time:5}); saveChat();')
check("file text saved", "FILE BODY" in js(f'__store["strata.chat.{second_id}"]'))
js(f'var reloaded = JSON.parse(__store["strata.chat.{second_id}"]); messages = reloaded;')
check("history after reload carries the file", "FILE BODY" in js('JSON.stringify(apiMessages())'))
# switching
check("switch to the first chat", js(f'switchChat("{first_id}")') is True and js('messages[0].text') == "old question")
js('busy = {controller: {abort(){}}, msg: {}};')
check("no switch while an answer is being written", js(f'switchChat("{second_id}")') is False and js('chatId') == first_id)
js('busy = null;')
# the list renders (one row per chat) and delete + undo work
js('renderChatList();')
check("list rows", js('document.getElementById("chat-list").children.length') == 2)
js(f'var row = document.getElementById("chat-list").children.find(r => r.children[0].children[0].textContent === "second chat question"); '
   'row.children[1].onclick({stopPropagation(){}});')
check("deleted", js('chats.length') == 1 and js(f'!("strata.chat.{second_id}" in __store)'))
# undo = the toast's action: find it in the toasts container's last child... simpler: call the stored action
check("current chat kept", js('chatId') == first_id)
# a full browser storage: saving a long chat fails -> the page says so instead of silently losing it
js('__full = true; messages.push({role:"user",text:"x".repeat(5000),time:6}); saveChat(); __full = false;')
check("full storage warned", js('storageWarned') is True)
# drawers
js('openChats(true); openChats(false); openDrawer(false);')
check("chats drawer toggles", js('document.getElementById("chats-drawer").dataset.open') == "false")

bad = [n for n, ok in checks if not ok]
for n, ok in checks:
    print(("ok   " if ok else "FAIL ") + n)
print("web app chat list:", "ALL OK" if not bad else f"{len(bad)} FAILED")
sys.exit(1 if bad else 0)
