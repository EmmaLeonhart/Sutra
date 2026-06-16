(defn fst [v]
  (+ (nth v 0) (nth v 1)))

(defn main []
  (let [w [5 8]]
    (fst w)))
