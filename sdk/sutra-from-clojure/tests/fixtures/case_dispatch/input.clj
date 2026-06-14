(defn classify [x]
  (case x
    1 10
    2 20
    3 30
    99))

(defn main [] (+ (classify 2) (classify 7)))
