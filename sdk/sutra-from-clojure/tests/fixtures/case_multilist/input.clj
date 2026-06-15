(defn classify [x]
  (case x
    (1 3 5) 100
    (2 4) 200
    999))

(defn main [] (+ (classify 3) (classify 4)))
