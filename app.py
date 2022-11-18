from flask import Flask
from flask import request

import subprocess
import json

app = Flask(__name__)
host_addr = "0.0.0.0"
host_port = 8888

@app.route('/')
def hello():
    try:
        file = str(request.args.get("fileName"))
        code = str(request.args.get("sourceCode"))
        print(file)
        print(code)

        # make c file
        f = open(file + '.c', 'w')
        f.write(code)
        f.close()
        print("make file sucess")

        command = "python3 shell.py " + file
        result = subprocess.run(command.split(' '), stdout=subprocess.PIPE, text=True)
        # print(result.stdout)
        print("make run subprocess")

        print("get json")
        with open('result_' + file + '_temp.json', 'r') as f:
            json_data = json.load(f)

        print("send json")
        return (json.dumps(json_data))

        return result.stdout
        return "hello"
    except:
        return "error"

if __name__ == '__main__':
    app.run(debug=True, host=host_addr, port=host_port)