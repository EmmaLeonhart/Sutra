(defn grade [n]
  (cond
    (> n 90) 100
    (> n 50) 50
    :else 0))

(defn main [] (+ (grade 95) (grade 70)))
