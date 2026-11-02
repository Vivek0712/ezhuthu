"""AgentCore Runtime entry point (Direct Code Deploy).

AgentCore runs this file as a script from the root of the code bundle, so it must not use relative
imports. It loads the Strands agent app owned by the Agent team (src/ezhuthu/agentcore_app.py), which
must expose ``app = BedrockAgentCoreApp()`` with an ``@app.entrypoint`` that accepts the proxy payload
described in infra/README.md ("Proxy to agent contract"). ``start_warmup`` builds the restorer's parallel index and
5-gram in a background thread so the first request does not pay for them (issue #41).
"""

from ezhuthu.agentcore_app import app, start_warmup

if __name__ == "__main__":
    start_warmup()
    app.run()
