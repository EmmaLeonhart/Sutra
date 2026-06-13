(defn scale [x]
  (let [y (+ x 1)
        z (* y 2)]
    (+ z x)))

(defn main [] (scale 5))
