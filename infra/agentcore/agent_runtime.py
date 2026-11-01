"""AgentCore Runtime entry point (Direct Code Deploy).

AgentCore runs this file as a script from the root of the code bundle, so it must not use relative
imports. It loads the Strands agent app owned by the Agent team (src/ezhuthu/agentcore_app.py), which
must expose ``app = BedrockAgentCoreApp()`` with an ``@app.entrypoint`` that accepts the proxy payload
described in infra/README.md ("Proxy to agent contract").
"""

from ezhuthu.agentcore_app import app

if __name__ == "__main__":
    app.run()
