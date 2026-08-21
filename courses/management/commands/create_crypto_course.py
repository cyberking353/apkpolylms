"""
Management command: python manage.py create_crypto_course

Creates the 'Cryptographic Applications' course (HND2, CSC+CS) from the
official lecture note: 8 modules, 18 lectures (video links left empty for the
lecturer to fill) and 8 weekly quizzes with 37 multiple-choice questions.

Idempotent: safe to run more than once - existing records are reused.
"""
from django.core.management.base import BaseCommand

from courses.models import Course, Module, Lecture, CourseDepartment, Category
from quizzes.models import Quiz, Question, Choice


class Command(BaseCommand):
    help = 'Create the Cryptographic Applications course (8 modules + quizzes), idempotently'

    def handle(self, *args, **options):

        course, created = Course.objects.get_or_create(
            slug='cryptographic-applications',
            defaults=dict(
                title='Cryptographic Applications',
                code='CYS-HND2',
                category=Category.objects.filter(name='Computer Science').first(),
                description=(
                    'Based on the official HND II Cyber Security lecture note. Covers the fundamentals of '
                    'cryptography, real-world applications (HTTPS, messaging, banking, blockchain), the role of '
                    'cryptography in cyber security, and five fully worked algorithms: Caesar, Vigenere, XOR, '
                    'Hill and RSA - with step-by-step encryption and decryption calculations.'),
                icon='lock', color_start='#1E1B4B', color_end='#4C1D95',
                level='HND2', semester='1', credit_unit=3,
                duration_hours=12,
                status='published',
            ),
        )
        if created:
            CourseDepartment.objects.create(course=course, department='CSC', is_home=True)
        self.stdout.write(f'course: {course.title} | created: {created}')

        MODULES = [
            ("Fundamentals of Cryptography", "What cryptography is and the security goals it achieves", [
                ("What is Cryptography?", "Definition: protecting information by transforming it so only authorised parties can understand it. Combines mathematics, computer science and engineering. Why it underpins HTTPS, private messaging, password storage, digital banking and blockchain.", 12),
                ("The Five Security Goals", "The CIA triad plus authentication and non-repudiation: Confidentiality (encryption), Integrity (hashing/MACs), Availability (supported by key management), Authentication (signatures, certificates) and Non-repudiation (digital signatures).", 15),
            ]),
            ("Cryptographic Terminology and Classification", "Key terms and the three families of cryptographic techniques", [
                ("Essential Terminology", "Plaintext, ciphertext, encryption, decryption, key, cipher/algorithm, cryptanalysis, key space and cryptology - the vocabulary every security professional uses.", 10),
                ("Symmetric vs Asymmetric vs Hashing", "Symmetric-key (one shared key: DES, 3DES, AES, Caesar, Vigenere) and its key-distribution problem; asymmetric/public-key (key pairs: RSA, Diffie-Hellman, ECC); hash functions (one-way digests: MD5, SHA-1, SHA-256, SHA-3).", 18),
            ]),
            ("Cryptography in the Real World", "Systems you use every day that depend on cryptography", [
                ("Everyday Systems", "HTTPS/TLS (RSA/ECC + AES hybrid), WhatsApp & Signal end-to-end encryption (Signal Protocol), online banking/ATM (AES, RSA, HMAC), Wi-Fi security WPA2/WPA3 (AES-CCMP).", 14),
                ("Blockchain, VPNs and Password Storage", "Bitcoin (SHA-256, ECDSA), VPN tunnels (AES, IPSec, Diffie-Hellman), and password storage in databases using bcrypt, SHA-256 or Argon2 so plaintext is never saved.", 14),
            ]),
            ("Applications in Cyber Security", "How cryptography is applied across the security discipline", [
                ("Secure Communication and Data at Rest", "Protecting email, chat and calls from eavesdropping; encrypting stored data on disks, USB drives, databases and cloud storage (BitLocker, VeraCrypt, encrypted DB columns).", 12),
                ("Authentication, Signatures and Non-Repudiation", "Digital certificates, challenge-response authentication, MFA tokens; how digital signatures prove authorship and prevent senders denying their messages.", 12),
                ("E-Commerce, Code Signing and Network Defence", "Payment gateways and PCI-DSS compliance; code signing for software/firmware integrity; VPNs and encrypted tunnels for organisation-wide network security.", 12),
            ]),
            ("Classical Ciphers I - The Caesar Cipher", "Symmetric shift cipher with full worked example", [
                ("How the Shift Cipher Works", "Shifting each letter by a fixed key K using A=0..Z=25. Encryption C = (P + K) mod 26, decryption P = (C - K) mod 26. Why its tiny key space (25 keys) makes it insecure today.", 10),
                ("Worked Example: HELLO to KHOOR", "Step-by-step: H(7)+3=10->K, E(4)+3=7->H, L(11)+3=14->O, L->O, O(14)+3=17->R giving KHOOR; then decrypting back with subtraction mod 26.", 10),
            ]),
            ("Classical Ciphers II - The Vigenere Cipher", "Polyalphabetic cipher that defeats simple frequency analysis", [
                ("The Polyalphabetic Concept", "A repeating keyword where each letter specifies a different Caesar shift: Ci = (Pi + Ki) mod 26. Why frequency analysis becomes much harder than with Caesar.", 12),
                ("Worked Example: ATTACK with Key LEMON", "Full calculation: A+L=L, T+E=X, T+M=F (31 mod 26 = 5), A+O=O, C+N=P, K+L=V giving LXFOPV, plus the decryption back to ATTACK.", 12),
            ]),
            ("Bitwise and Matrix Ciphers - XOR and Hill", "Stream-cipher building block and linear-algebra cipher", [
                ("The XOR Cipher and One-Time Pad", "XOR as its own inverse: (P XOR K) XOR K = P. Worked byte example: 'H' (01001000) XOR 'K' (01001011) = 00000011. Why the key must be as long and random as the message.", 12),
                ("The Hill Cipher - Matrix Multiplication Mod 26", "Encrypting blocks with a key matrix: HI -> [7,8], C = K x P mod 26 gives TC. Decryption via the inverse matrix using det(K)=9 and 9^-1 mod 26 = 3.", 15),
            ]),
            ("RSA Public-Key Cryptography", "The asymmetric algorithm securing the internet", [
                ("How RSA Works", "Key generation: choose primes p,q; compute n=pq and phi(n)=(p-1)(q-1); pick e coprime to phi; find d with ed = 1 mod phi. Public key (e,n), private key (d,n).", 15),
                ("Worked Example: p=3, q=11, M=2", "n=33, phi=20, e=7, d=3. Encryption C = 2^7 mod 33 = 29; decryption M = 29^3 mod 33 = 2. Every modular step shown.", 12),
                ("Hybrid Encryption and Where RSA Fits", "Why RSA is too slow for bulk data: it protects a symmetric session key instead (as in TLS), and creates digital signatures. Factoring large primes is the hardness assumption.", 10),
            ]),
        ]

        QUIZZES = [
            [("What does cryptography primarily protect?", ["Information confidentiality, integrity and authenticity", "Network bandwidth", "Hardware performance", "User interface design"], 0),
             ("Which goal ensures a sender cannot deny having sent a message?", ["Confidentiality", "Integrity", "Non-repudiation", "Availability"], 2),
             ("Ensuring data has not been altered in transit is achieved through:", ["Encryption only", "Hashing/MACs", "Compression", "Redundancy"], 1),
             ("HTTPS, digital banking and blockchain all rely fundamentally on:", ["Cryptography", "Firewalls alone", "Antivirus software", "Load balancers"], 0)],
            [("The unreadable output of encryption is called:", ["Plaintext", "Ciphertext", "Digest", "Salt"], 1),
             ("The study of breaking ciphers without the key is:", ["Cryptology", "Encoding", "Cryptanalysis", "Steganography"], 2),
             ("Which technique uses ONE shared key for both encryption and decryption?", ["Asymmetric cryptography", "Hash functions", "Symmetric cryptography", "Digital signatures"], 2),
             ("Which of these is NOT reversible?", ["AES encryption", "Caesar cipher", "SHA-256 hashing", "RSA encryption"], 2),
             ("The key-distribution problem is solved by:", ["Longer passwords", "Public-key cryptography", "Faster CPUs", "Compression"], 1)],
            [("Which protocol secures the padlock icon in browsers?", ["FTP", "HTTPS/TLS", "SMTP", "DNS"], 1),
             ("WhatsApp's end-to-end encryption uses the:", ["Signal Protocol", "WEP protocol", "Telnet", "SMB protocol"], 0),
             ("Wi-Fi traffic in WPA2/WPA3 is encrypted with:", ["DES", "RC4", "AES-CCMP", "ROT13"], 2),
             ("Bitcoin's mining and transaction security relies on:", ["SHA-256 and ECDSA", "MD5 and ROT13", "Caesar cipher", "Base64"], 0),
             ("Passwords should be stored in databases using:", ["Plaintext", "Reversible encryption only", "Hash functions like bcrypt/Argon2", "Spreadsheets"], 2)],
            [("Encrypting data on hard disks and USB drives protects:", ["Data at rest", "Data in transit only", "Metadata only", "Network speed"], 0),
             ("Proving a document came from a claimed sender uses:", ["Compression", "Digital signatures", "ZIP archives", "VPNs"], 1),
             ("PCI-DSS compliance in payment gateways relates to:", ["Protecting card details with cryptography", "Website colours", "Server rack size", "Email marketing"], 0),
             ("Code signing confirms that software updates are:", ["Genuine and untampered", "Free of charge", "Open source", "Fast to download"], 0),
             ("Salting password hashes means:", ["Adding random data before hashing", "Compressing passwords", "Encrypting with AES", "Using short passwords"], 0)],
            [("In the Caesar cipher with A=0, encrypting P with key K uses:", ["C = (P + K) mod 26", "C = P x K", "C = P - K", "C = P XOR K"], 0),
             ("With key K=3, HELLO becomes:", ["KHOOR", "JGNNQ", "LIPPS", "HELLO"], 0),
             ("Decrypting KHOOR with K=3 gives:", ["WORLD", "HELLO", "CRYPT", "SHIFT"], 1),
             ("The Caesar cipher is insecure because:", ["It uses mathematics", "Its key space is only 25 possible shifts", "Computers cannot process it", "It needs long keys"], 1)],
            [("The Vigenere cipher improves on Caesar by using:", ["Bigger alphabets", "A repeating keyword giving different shifts per letter", "No keys at all", "Numbers instead of letters"], 1),
             ("With key LEMON, the first plaintext letter A(0) shifted by L(11) gives:", ["A", "L", "Z", "M"], 1),
             ("In ATTACK + LEMON, T(19)+M(12) = 31 reduces to:", ["5 -> F", "31 -> F", "7 -> H", "3 -> D"], 0),
             ("Why is Vigenere harder to break than Caesar?", ["Frequency analysis is much harder with multiple shift values", "It uses computers", "It has no ciphertext", "Letters are removed"], 0)],
            [("Which property makes XOR convenient for encryption?", ["It is its own inverse", "It always outputs zero", "It requires no key", "It compresses data"], 0),
             ("'H' (01001000) XOR 'K' (01001011) equals:", ["00000011", "11111100", "01000011", "10001011"], 0),
             ("A one-time pad is unbreakable when the key is:", ["Short and reused", "As long as and as random as the message", "Published publicly", "A single letter"], 1),
             ("In the Hill cipher, encryption is performed with:", ["Matrix multiplication mod 26", "Letter substitution only", "Bit shifting", "Prime factorisation"], 0),
             ("For the Hill key [[3,3],[2,5]] encrypting HI gave:", ["TC", "CT", "HI", "OK"], 0)],
            [("RSA's security rests on the difficulty of:", ["Sorting large lists", "Factoring the product of two large primes", "Hashing passwords", "Compressing images"], 1),
             ("With p=3, q=11, what is n?", ["33", "8", "14", "30"], 0),
             ("phi(n) for p=3, q=11 is:", ["20", "33", "10", "6"], 0),
             ("With public key (e=7, n=33), encrypting M=2 gives C =", ["29", "128", "16", "2"], 0),
             ("Because RSA is slow for bulk data, TLS typically uses it to:", ["Encrypt entire videos", "Protect a symmetric session key (hybrid encryption)", "Replace hashing", "Speed up Wi-Fi"], 1)],
        ]

        week = 0
        for (m_title, m_desc, lectures), qs in zip(MODULES, QUIZZES):
            week += 1
            module, mc = Module.objects.get_or_create(
                course=course, week_number=week,
                defaults={'title': m_title, 'description': m_desc})
            order = 0
            for (l_title, l_desc, mins) in lectures:
                order += 1
                Lecture.objects.get_or_create(
                    module=module, title=l_title,
                    defaults={'video_url': '', 'duration_minutes': mins, 'order': order})
            quiz, qc = Quiz.objects.get_or_create(
                module=module, course=course,
                defaults={'title': f'Week {week} Quiz: {m_title.split(" - ")[0].split(":")[0]}',
                          'time_limit_minutes': 10, 'pass_mark': 50})
            order = 0
            for (text, choices, correct_idx) in qs:
                order += 1
                q, q_created = Question.objects.get_or_create(
                    quiz=quiz, text=text, defaults={'order': order})
                if q_created:
                    for i, c_text in enumerate(choices):
                        Choice.objects.create(question=q, text=c_text,
                                              is_correct=(i == correct_idx), order=i + 1)
            self.stdout.write(f'  W{week}: {m_title[:45]:45} | {len(lectures)} lectures | {len(qs)} questions')

        total_q = Question.objects.filter(quiz__course=course).count()
        self.stdout.write(self.style.SUCCESS(
            f'DONE: {Module.objects.filter(course=course).count()} modules, '
            f'{Lecture.objects.filter(module__course=course).count()} lectures, '
            f'{Quiz.objects.filter(course=course).count()} quizzes, {total_q} questions'))
