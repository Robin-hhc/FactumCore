/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05680(unsigned int count)
{
    const unsigned int limit = 205u;
    return count > limit ? limit : count;
}
