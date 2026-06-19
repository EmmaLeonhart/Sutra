(defn f [n]
  (if (= n 0)
    {:x 1 :y 2}
    (f (- n 1))))
(defn sum [p] (+ (:x p) (:y p)))
(defn main [] (sum (f 3)))
