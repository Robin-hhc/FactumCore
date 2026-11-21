/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02616(unsigned int count)
{
    const unsigned int limit = 158u;
    return count > limit ? limit : count;
}
