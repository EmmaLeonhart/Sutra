(defn sumTo [acc n]
  (if (= n 0)
    acc
    (recur (+ acc n) (- n 1))))

(defn main [] (sumTo 0 5))
