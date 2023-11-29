1 2 3
# Carcan Calin 334CD - Tema1 RL

## 1. Tabela de comutare
    Pentru implementarea tabelei de comutare am folosit un dictionar in care retineam MAC-ul sursa am frame-ului si interfata pe care a venit pentru a putea retine drumurile catre celelalte device-uri cu care switch-ul intra in contact.
    Mai departe am implementat algoritmul in pseudocod prezentat in cerinta task-ului.
## 2. Functionalitati VLAN
    Pentru a putea implementa functionalitati de VLAN-uri a trebuit sa folosesc un alt dictionar in care legam numele interfetelor citite din fisierul .cfg de VLAN-urile acestora si sa modific pseudocodul initial in cazurile in care frame-ul venea de pe o legatura trunk sau acces si in cazurile in care se ducea mai departe pe o legatura trunk sau acces in modul in care au fost prezentate in cerinta task-ului. Am tratat cazurile in care frame-ul a venit de pe o anumita legatura in functiile trunk_forwarding() si acces_forwarding(). Deoarece atunci cand frame-urile veneau de la host-uri nu veneau cu tag-ul de VLAN deja specificat a trebuit sa verific din ce VLAN sursa a venit mesajul si sa compar cu VLAN Tag-ul care putea sa fie pus in mesaj pentru a decide in ce VLAN-uri are frame-ul voia mai departe sa fie forward-at.
## 3. Implementare STP
    Pentru implementarea algoritmului de STP am alcatuit mesaje formate din MAC-ul special de STP, bid-ul switch-ului care trimite mesajul, bid-ul switch-ului root cunoscut de switch-ul sursa si costul drumului pana la acesta. aceste mesaje sunt trimise in continuu pe interfetele trunk ale fiecarui switch de catre un nou thread.
    Am identificat mesajele de tip BPDU dupa MAC-ul special si am tratat datele primite din aceste frame-uri exact ca in pseudocodul prezentat la ultima cerinta a temei. 