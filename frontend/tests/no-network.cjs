"use strict";

const blocked = (operation) => {
  throw new Error(`Offline test guard blocked ${operation}.`);
};

const deny = (operation) => {
  function deniedOperation() {
    return blocked(operation);
  }
  Object.defineProperty(deniedOperation, "__palnaviOfflineGuard", {
    value: true,
  });
  return deniedOperation;
};

const isDenied = (value) =>
  typeof value === "function" && value.__palnaviOfflineGuard === true;

globalThis.fetch = deny("global fetch");
if ("WebSocket" in globalThis) {
  globalThis.WebSocket = deny("WebSocket");
}

const net = require("node:net");
net.connect = deny("TCP connect");
net.createConnection = deny("TCP connection");
net.createServer = deny("TCP server");
net.Socket.prototype.connect = deny("TCP socket connect");
net.Server.prototype.listen = deny("TCP listen");

const tls = require("node:tls");
tls.connect = deny("TLS connect");
tls.TLSSocket.prototype.connect = deny("TLS socket connect");

const http = require("node:http");
http.request = deny("HTTP request");
http.get = deny("HTTP get");

const https = require("node:https");
https.request = deny("HTTPS request");
https.get = deny("HTTPS get");

const http2 = require("node:http2");
http2.connect = deny("HTTP/2 connect");

const dns = require("node:dns");
const dnsPromises = require("node:dns/promises");
const dnsOperations = [
  "lookup",
  "lookupService",
  "resolve",
  "resolve4",
  "resolve6",
  "resolveAny",
  "resolveCaa",
  "resolveCname",
  "resolveMx",
  "resolveNaptr",
  "resolveNs",
  "resolvePtr",
  "resolveSoa",
  "resolveSrv",
  "resolveTxt",
  "reverse",
];
for (const name of [
  ...dnsOperations,
]) {
  if (typeof dns[name] === "function") {
    dns[name] = deny(`DNS ${name}`);
  }
}
for (const name of dnsOperations) {
  if (typeof dns.promises[name] === "function") {
    dns.promises[name] = deny(`DNS promises ${name}`);
  }
  if (typeof dnsPromises[name] === "function") {
    dnsPromises[name] = deny(`DNS promises module ${name}`);
  }
  if (typeof dns.Resolver.prototype[name] === "function") {
    dns.Resolver.prototype[name] = deny(`DNS resolver ${name}`);
  }
  if (typeof dnsPromises.Resolver.prototype[name] === "function") {
    dnsPromises.Resolver.prototype[name] = deny(
      `DNS promises resolver ${name}`,
    );
  }
}

const dgram = require("node:dgram");
dgram.createSocket = deny("UDP socket");
dgram.Socket.prototype.bind = deny("UDP bind");

const childProcess = require("node:child_process");
for (const name of [
  "exec",
  "execFile",
  "execFileSync",
  "execSync",
  "fork",
  "spawn",
  "spawnSync",
]) {
  childProcess[name] = deny(`subprocess ${name}`);
}

require("node:module").syncBuiltinESMExports();

const requiredGuards = [
  globalThis.fetch,
  net.connect,
  net.createConnection,
  net.createServer,
  net.Socket.prototype.connect,
  net.Server.prototype.listen,
  dns.lookup,
  dns.lookupService,
  dnsPromises.lookup,
  dnsPromises.lookupService,
  dnsPromises.Resolver.prototype.resolve4,
  dgram.createSocket,
  dgram.Socket.prototype.bind,
  http.request,
  https.request,
  http2.connect,
  childProcess.spawn,
  childProcess.spawnSync,
];
if (!requiredGuards.every(isDenied)) {
  throw new Error("Offline test guard conformance audit failed.");
}
globalThis.__PALNAVI_OFFLINE_GUARD__ = true;
