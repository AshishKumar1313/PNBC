import os
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont


def create_sample_documents():
    output_dir = 'sample_documents'
    os.makedirs(output_dir, exist_ok=True)

    # -------------------------------------------------------------
    # Sample 1: Standard Multiple Choice Questions with Inline Answers
    # -------------------------------------------------------------
    doc1 = fitz.open()
    page1 = doc1.new_page(width=595, height=842)  # A4
    text1 = """PRAGATI BHARATI ALL-INDIA APTITUDE TEST
Subject: Computer Science & General Intelligence
Duration: 60 Minutes

1. Which data structure operates on a Last In First Out (LIFO) principle?
   (A) Queue
   (B) Stack
   (C) Binary Search Tree
   (D) Linked List
   Ans: B
   Explanation: A Stack is a linear data structure that follows the LIFO principle.

2. What is the average time complexity of searching an element in a balanced Binary Search Tree?
   (A) O(1)
   (B) O(n)
   (C) O(log n)
   (D) O(n^2)
   Answer: (C)

3. Which of the following networking protocols is connection-oriented?
   (A) UDP
   (B) IP
   (C) ICMP
   (D) TCP
   Ans: D
"""
    page1.insert_text((50, 70), text1, fontsize=11, fontname='helv')
    doc1.save(os.path.join(output_dir, 'sample_1_standard_mcq.pdf'))
    doc1.close()

    # -------------------------------------------------------------
    # Sample 2: Question Spanning Across Multiple Pages
    # -------------------------------------------------------------
    doc2 = fitz.open()
    # Page 1
    p1 = doc2.new_page(width=595, height=842)
    p1_text = """EXAMINATION PAPER: ADVANCED ALGORITHMS
Section A: Theory

1. Define asymptotic notation and explain Big-O notation.
   (A) Upper bound on running time
   (B) Lower bound on running time
   (C) Exact bound on running time
   (D) None of the above
   Ans: A

2. In a distributed consensus protocol running across multiple unreliable network partitions, which of the following guarantees cannot be simultaneously satisfied according to Brewer's CAP theorem when network partitioning occurs?"""
    p1.insert_text((50, 70), p1_text, fontsize=11, fontname='helv')

    # Page 2 continues question 2 options and adds question 3
    p2 = doc2.new_page(width=595, height=842)
    p2_text = """(A) Consistency and Latency
(B) Consistency and Availability
(C) Partition Tolerance and Durability
(D) Atomicity and Isolation
Ans: B

3. Which sorting algorithm exhibits the best worst-case performance among comparison sorts?
(A) Quick Sort
(B) Merge Sort
(C) Bubble Sort
(D) Insertion Sort
Ans: B
"""
    p2.insert_text((50, 70), p2_text, fontsize=11, fontname='helv')
    doc2.save(os.path.join(output_dir, 'sample_2_multipage_spanning.pdf'))
    doc2.close()

    # -------------------------------------------------------------
    # Sample 3: Document with an End Answer Key Section
    # -------------------------------------------------------------
    doc3 = fitz.open()
    # Page 1: Questions
    p3_1 = doc3.new_page(width=595, height=842)
    p3_1_text = """PRAGATI BHARATI SCHOLARSHIP EXAMINATION
Part I: General Science

1. What is the SI unit of electric current?
   (A) Volt
   (B) Ampere
   (C) Ohm
   (D) Watt

2. Which planet in our solar system is known as the Red Planet?
   (A) Venus
   (B) Saturn
   (C) Mars
   (D) Jupiter

3. What is the primary gas found in the Earth's atmosphere?
   (A) Oxygen
   (B) Carbon Dioxide
   (C) Nitrogen
   (D) Hydrogen
"""
    p3_1.insert_text((50, 70), p3_1_text, fontsize=11, fontname='helv')

    # Page 2: Answer Key at the end
    p3_2 = doc3.new_page(width=595, height=842)
    p3_2_text = """4. What is the chemical formula for water?
   (A) CO2
   (B) NaCl
   (C) CH4
   (D) H2O

5. Sound waves cannot travel through which of the following mediums?
   (A) Steel
   (B) Water
   (C) Vacuum
   (D) Air

============================================================
ANSWER KEY
============================================================
1. B
2. C
3. C
4. D
5. C
"""
    p3_2.insert_text((50, 70), p3_2_text, fontsize=11, fontname='helv')
    doc3.save(os.path.join(output_dir, 'sample_3_with_end_answer_key.pdf'))
    doc3.close()

    # -------------------------------------------------------------
    # Sample 4: Standalone Separate Answer Key Document
    # -------------------------------------------------------------
    doc4 = fitz.open()
    p4 = doc4.new_page(width=595, height=842)
    p4_text = """OFFICIAL ANSWER KEY & SOLUTIONS
Document Reference: Computer Science Set-B

ANSWER KEY:
1. B
2. C
3. D
4. A
5. B
"""
    p4.insert_text((50, 70), p4_text, fontsize=12, fontname='helv')
    doc4.save(os.path.join(output_dir, 'sample_4_separate_answer_key.pdf'))
    doc4.close()

    # -------------------------------------------------------------
    # Sample 5: Question Paper as an Image (PNG)
    # -------------------------------------------------------------
    img = Image.new('RGB', (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Draw simple text simulating image exam paper
    image_text = (
        "PRAGATI BHARATI SAMPLE IMAGE EXAM\n\n"
        "1. What does CPU stand for?\n"
        "   (A) Central Process Unit\n"
        "   (B) Central Processing Unit\n"
        "   (C) Computer Personal Unit\n"
        "   (D) Control Processing Unit\n"
        "   Ans: B\n\n"
        "2. Which memory is volatile in nature?\n"
        "   (A) ROM\n"
        "   (B) RAM\n"
        "   (C) Flash Memory\n"
        "   (D) Hard Disk\n"
        "   Ans: B\n"
    )
    draw.text((40, 40), image_text, fill=(0, 0, 0))
    img.save(os.path.join(output_dir, 'sample_5_scanned_image.png'))

    # -------------------------------------------------------------
    # Sample 6: Noisy / Low Confidence Imperfect Document
    # -------------------------------------------------------------
    doc6 = fitz.open()
    p6 = doc6.new_page(width=595, height=842)
    p6_text = """IMPERFECT ENTRANCE TEST (POOR FORMATTING & OMISSIONS)

1. Who
   (A) Alan Turing
   (B) Ada Lovelace
   (D) Charles Babbage

5. In thermodynamics, absolute zero temperature is:
   (A) 0 Kelvin
   (B) -273.15 Celsius
"""
    p6.insert_text((50, 70), p6_text, fontsize=11, fontname='helv')
    doc6.save(os.path.join(output_dir, 'sample_6_noisy_low_confidence.pdf'))
    doc6.close()

    # -------------------------------------------------------------
    # Sample 7: Invalid / Corrupted Document
    # -------------------------------------------------------------
    with open(os.path.join(output_dir, 'sample_invalid.pdf'), 'wb') as f:
        f.write(b'This is a completely plain text file masquerading as a PDF without magic bytes.')

    print(f'Sample documents successfully generated in {output_dir}/')


if __name__ == '__main__':
    create_sample_documents()
