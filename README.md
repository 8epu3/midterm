# Calculator

## Running Project 

---

### 1. Clone the Repository

```bash
git clone git@github.com:8epu3/midterm.git
cd midterm
```

---

### 2. Create Virtual Environment


```bash
python -m venv venv
source .venv/bin/activate
```

### 3. Install Dependencies


```bash
pip install -r requirements.txt
```

### 4. Running the Project


```bash
python main.py
```

---

## Running Tests


```bash
pytest --cov=app tests/ --cov-report=term-missing
```
