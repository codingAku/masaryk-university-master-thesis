# Master's Thesis Research - Masaryk University.
Master's thesis research for Masaryk University, 2024. Mainly aiming for the development of an educational tool on requirement elicitation.

# Stakebot 

There is a chat application built with Streamlit that integrates with ChatOllama (via LangChain) and provides a modern chat UI. It includes features such as model selection via a dropdown, user profile management, and dynamic chat history clearing.

![image](https://github.com/user-attachments/assets/87b5dc2f-d2bd-4ace-9e71-92b7bb150cdd)


## Features

- **Dynamic Chat Interface:**  
  Uses `streamlit-chat` to display chat messages.
  
- **User Profile Management:**  
  Select a user from a set of mock profiles to update the persona information displayed on the app.

- **Model Selection:**  
  A dropdown in the top-right allows you to select the model. The app attempts to fetch available models using the `ollama list` command.

- **Chat History Management:**  
  Clear the chat history with a button and update it when the user or model is changed.

## Setup Locally

### Prerequisites

- Docker engine installed.

### Installation

Follow these steps to install and run the project:

1. **Clone the repository and navigate to it:**

 ```bash
 git clone https://github.com/codingAku/masaryk-university-master-thesis
 cd masaryk-university-master-thesis
 ```
   
2. **Run docker-compose**
 
```bash
docker-compose up --build
```
3. **Go to application port**

  [Stakebot](http://localhost:8501)

4. **Voice Generation**
   
In this state, you can run the application chat-only. In order to start voice generation, you need to clone the following repository:

 ```bash
 git clone https://github.com/metavoiceio/metavoice-src
 ```

Assuming you are still in masaryk-university-master-thesis directory, clone the metavoice configuration files to the cloned repository:
 ```bash
 cd metavoice-configuration
copy "docker-compose.yml" "<your-metavoice-src-cloned-repo"
 ```

Navigate to metavoice-src repository and run the metavoice container:
```bash
cd <your-metavoice-src-cloned-repo>
docker-compose build
docker-compose up server
```

Now the voice generation will be available:
![image](https://github.com/user-attachments/assets/78075d13-c79d-4353-a26b-21333a63bf71)

Go to application port and use the application:  [Stakebot](http://localhost:8501)

---------
## Setup in Aura 

The voice generation takes about 15 min in a machine with 32 GB RAM. **Voice generation is recommended to run in a server with high computational power.**
In order to run the whole application in [Aura](https://www.fi.muni.cz/tech/unix/aura.html.cs):

1. **Clone the repository and navigate to it:**

 ```bash
 git clone https://github.com/codingAku/masaryk-university-master-thesis
 cd masaryk-university-master-thesis
 ```
   
3. **Run podman-compose**
 
```bash
podman-compose up --build
```

4. **Set up SSH tunnel to use the application in your local browser session**
   
```bash
  ssh -L 8501:localhost:8501 <faculty_login_username>@2001:718:801:230::17 
```

3. **Go to application port**

  [Stakebot](http://localhost:8501)

In order to set up voice generation in Aura server:

 ```bash
 git clone https://github.com/metavoiceio/metavoice-src
 ```

Assuming you are still in masaryk-university-master-thesis directory, clone the metavoice configuration files to the cloned repository:

 ```bash
 cd metavoice-configuration
cp "podman-compose.yml" "<your-metavoice-src-cloned-repo>"
cp "fast_inference_utils.py" "<your-metavoice-src-cloned-repo>/fam/llm"
 ```

Change line 19 in chat_helpers.py in main repository to following URL:

 ```bash
 cd ..
cat chat_helpers.py
 ```
URL: "http://10.0.2.2:58004/tts"


Run the main containers again:
```bash
podman-compose up
```

Run metavoice container:
```bash
cd <your-metavoice-src-cloned-repo>
podman-compose build
podman-compose up server
```

3. **Go to application port (SSH tunnelling still active)**

  [Stakebot](http://localhost:8501)


## Author
- Ecenur Sezer
