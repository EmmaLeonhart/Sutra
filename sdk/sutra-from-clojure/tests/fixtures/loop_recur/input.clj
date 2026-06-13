(defn sumLoop [n]
  (loop [acc 0 i 0]
    (if (< i n)
      (recur (+ acc i) (+ i 1))
      acc)))

(defn main [] (sumLoop 6))
