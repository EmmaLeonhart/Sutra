(defn sum2 [p]
  (+ (:x p) (:y p)))

(defn main []
  (sum2 {:x 5 :y 8}))
