def extract_text_pymupdf(file_path: str) -> str:
    text = ""
    try:
        import fitz

        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception:
        text = ""
    return text


def extract_text_pdfplumber(file_path: str) -> str:
    text = ""
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    except Exception:
        text = ""
    return text


def extract_text(file_path: str) -> str:
    text = extract_text_pymupdf(file_path)

    if not text or len(text.strip()) < 50:
        text = extract_text_pdfplumber(file_path)

    return text.strip()


def parse_jd(text: str) -> dict:
    lines = text.lower().split("\n")

    role = ""
    keywords = []
    requirements = []

    for line in lines:
        if any(x in line for x in ["engineer", "analyst", "manager", "developer"]):
            if not role:
                role = line.strip()

        if any(k in line for k in ["requirement", "responsibility", "must", "should"]):
            requirements.append(line.strip())

    for word in text.split():
        if word.istitle() or word.isupper():
            keywords.append(word.lower())

    return {
        "role": role,
        "requirements": list(set(requirements))[:20],
        "keywords": list(set(keywords))[:30],
    }


def parse_resume(text: str) -> dict:
    lines = text.split("\n")

    skills = []
    experience = []
    education = []

    for line in lines:
        l = line.lower()

        if any(k in l for k in ["python", "sql", "excel", "analysis", "machine learning"]):
            skills.append(line.strip())

        if "experience" in l or "worked" in l:
            experience.append(line.strip())

        if any(k in l for k in ["bsc", "msc", "degree", "bachelor", "master"]):
            education.append(line.strip())

    return {
        "skills": list(set(skills))[:20],
        "experience": experience[:10],
        "education": education[:5],
    }


def process_documents(resume_path: str, jd_path: str) -> dict:
    resume_text = extract_text(resume_path)
    jd_text = extract_text(jd_path)

    return {
        "resume": parse_resume(resume_text),
        "jd": parse_jd(jd_text),
        "raw": {
            "resume_text": resume_text,
            "jd_text": jd_text,
        },
    }
