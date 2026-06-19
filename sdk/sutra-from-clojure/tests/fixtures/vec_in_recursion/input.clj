(defn f [n]
  (if (= n 0)
    [10 20 30]
    (f (- n 1))))
(defn sum3 [v] (+ (+ (nth v 0) (nth v 1)) (nth v 2)))
(defn main [] (sum3 (f 2)))
