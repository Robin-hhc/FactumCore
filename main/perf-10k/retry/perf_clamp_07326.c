/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07326(unsigned int count)
{
    const unsigned int limit = 50u;
    return count > limit ? limit : count;
}
