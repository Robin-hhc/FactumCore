/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01862(unsigned int count)
{
    const unsigned int limit = 39u;
    return count > limit ? limit : count;
}
