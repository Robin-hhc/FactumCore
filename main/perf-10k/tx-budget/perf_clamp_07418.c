/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07418(unsigned int count)
{
    const unsigned int limit = 120u;
    return count > limit ? limit : count;
}
