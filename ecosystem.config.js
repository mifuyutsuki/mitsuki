module.exports = {
  apps : [{
    name          : "mitsuki",
    script        : "./run.py",
    interpreter   : "./.venv/bin/python",
    restart_delay : 30000,
    kill_timeout  : 5000
  }]
}