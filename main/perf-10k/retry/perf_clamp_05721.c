/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05721(unsigned int count)
{
    const unsigned int limit = 155u;
    return count > limit ? limit : count;
}
