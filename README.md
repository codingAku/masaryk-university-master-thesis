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

## Setup

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


## Author
- Ecenur Sezer
