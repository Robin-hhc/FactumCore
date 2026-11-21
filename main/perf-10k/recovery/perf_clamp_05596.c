/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05596(unsigned int count)
{
    const unsigned int limit = 22u;
    return count > limit ? limit : count;
}
